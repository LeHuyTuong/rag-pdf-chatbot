import re
import unicodedata

from app.core.config import Settings
from app.core.logging import get_logger
from app.infrastructure.qdrant.qdrant_service import QdrantService
from app.models.schemas import Chunk, RagAskRequest, RagAskResponse, RetrievedChunk, Source, utc_now
from app.services.embedding.embedding_service import EmbeddingService
from app.services.llm.llm_service import LlmService, REFUSAL
from app.services.mysql_service import MySqlService
from app.services.reports.chunk_report_service import ChunkReportService
from app.services.retrieval.retrieval_service import RetrievalService
from app.services.retrieval.reranking_service import RerankingService

logger = get_logger(__name__)

INSUFFICIENT_CONTEXT_ANSWER = 'Tai lieu hien co chua cung cap du thong tin dang tin cay de tra loi cau hoi nay.'
NO_CHUNKS_ANSWER = 'Tai lieu hien tai chua co doan noi dung nao co the dung de tra loi. Vui long kiem tra lai qua trinh ingest/OCR cua tai lieu.'
PARTIAL_PREFIX = 'Dua tren cac doan tai lieu hien co, co the tom tat so bo: '
PARTIAL_MIN_CONFIDENCE = 0.50
PARTIAL_MAX_CONFIDENCE = 0.65


class RagPipeline:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.reports = ChunkReportService(settings)

    def ask(self, request: RagAskRequest) -> RagAskResponse:
        logger.info(
            'rag ask start message_id=%s document_id=%s user_id=%s',
            request.message_id,
            request.document_id,
            request.user_id,
        )
        retrieved = self._retrieve(request)
        selected = [result for result in retrieved if result.selected_for_context][: self.settings.max_context_chunks]
        answer, confidence, answer_type, warning = self._build_answer(request, retrieved, selected)
        answer_type, confidence, warning = self._normalize_answer_type(answer, confidence, answer_type, warning)

        evidence_results = selected if answer_type in ('answered', 'partial_answer') else []
        related_results = self._related_results(retrieved, evidence_results, answer_type)
        if answer_type == 'answered' and not evidence_results:
            answer_type = 'insufficient_context' if related_results else 'out_of_scope'
        retrieval_path = self._write_retrieval_report(request, retrieved, selected)
        answer_path = self._write_answer_report(
            request,
            retrieved,
            evidence_results,
            answer,
            confidence,
            warning,
            answer_type,
            related_results,
        )
        sources = [self._source_from_result(result) for result in evidence_results]
        related_chunks = [self._source_from_result(result) for result in related_results]
        suggested_questions = self._suggested_questions(request, answer_type, evidence_results or related_results)

        logger.info(
            'rag ask complete message_id=%s retrieved=%s selected=%s confidence=%s answer_type=%s',
            request.message_id,
            len(retrieved),
            len(selected),
            confidence,
            answer_type,
        )
        return RagAskResponse(
            answer=answer,
            confidence=confidence,
            sources=sources if answer_type in ('answered', 'partial_answer') else [],
            related_chunks=related_chunks,
            suggested_questions=suggested_questions,
            answer_type=answer_type,
            warning=warning,
            retrieval_report_path=retrieval_path,
            answer_report_path=answer_path,
        )

    def _suggested_questions(self, request: RagAskRequest, answer_type: str, results: list[RetrievedChunk]) -> list[str]:
        if answer_type in ('insufficient_context', 'out_of_scope'):
            return [
                'Noi dung chinh cua tai lieu nay la gi?',
                'Tom tat cac chu de co trong tai lieu nay',
            ]
        text = ' '.join(result.chunk.content[:500] for result in results[:3])
        normalized = self._normalize_text(text)
        suggestions = []
        if 'kinh te luong' in normalized:
            suggestions.append('Kinh te luong duoc dinh nghia nhu the nao?')
        if 'hoi quy' in normalized:
            suggestions.append('Mo hinh hoi quy trong tai lieu nay co y nghia gi?')
        if 'phuong sai' in normalized or 'sai so' in normalized:
            suggestions.append('Phuong sai sai so thay doi la gi?')
        if self._is_overview_question(request.question):
            suggestions.append('Tai lieu nay co nhung chuong hoac chu de nao?')
        suggestions.append('Tom tat ngan gon cac y chinh lien quan')
        deduped = []
        for item in suggestions:
            if item not in deduped:
                deduped.append(item)
        return deduped[:3]

    def _retrieve(self, request: RagAskRequest) -> list[RetrievedChunk]:
        if self._is_overview_question(request.question):
            overview = self._overview_results(request)
            if overview:
                return overview
        retrieval = RetrievalService(self.settings, QdrantService(self.settings, EmbeddingService(self.settings)))
        retrieved = retrieval.retrieve(request.user_id, request.document_id, request.question)
        return RerankingService().rerank(retrieved)

    def _build_answer(self, request: RagAskRequest, retrieved: list[RetrievedChunk], selected: list[RetrievedChunk]) -> tuple[str, float, str, str | None]:
        selected_chunks = [result.chunk for result in selected]
        if not selected_chunks:
            if not retrieved:
                return NO_CHUNKS_ANSWER, 0.0, 'insufficient_context', 'No chunks were retrieved. The document may have zero chunks, scan-only content, or ingestion failed.'
            top_score = max((result.final_score for result in retrieved), default=0.0)
            answer_type = 'out_of_scope' if top_score < 0.35 else 'insufficient_context'
            return INSUFFICIENT_CONTEXT_ANSWER, min(top_score, 0.25), answer_type, 'No chunk met MIN_SCORE; refusing to answer to avoid hallucination.'

        confidence = round(sum(result.final_score for result in selected) / len(selected), 4)
        if self._is_overview_question(request.question):
            answer = self._overview_answer(request, selected_chunks)
            answer_type = 'partial_answer' if confidence < PARTIAL_MAX_CONFIDENCE else 'answered'
            return self._partialize(answer, answer_type), confidence, answer_type, None

        has_weak_context = any(self._support_level(result.final_score) == 'weak' for result in selected)
        if confidence < PARTIAL_MIN_CONFIDENCE and has_weak_context:
            return INSUFFICIENT_CONTEXT_ANSWER, min(confidence, 0.49), 'insufficient_context', 'Selected chunks were weak or below the confidence threshold; refusing to answer to avoid hallucination.'

        answer = LlmService(self.settings).answer(request.question, selected_chunks)
        if self._is_insufficient_answer(answer):
            return answer, min(confidence, 0.25), 'insufficient_context', 'LLM refused because the selected context was insufficient.'

        answer_type = 'partial_answer' if PARTIAL_MIN_CONFIDENCE <= confidence < PARTIAL_MAX_CONFIDENCE else 'answered'
        return self._partialize(answer, answer_type), confidence, answer_type, None

    def _normalize_answer_type(self, answer: str, confidence: float, answer_type: str, warning: str | None) -> tuple[str, float, str | None]:
        if self._is_insufficient_answer(answer):
            return 'insufficient_context', min(confidence, 0.25), warning or 'Answer text indicates insufficient context.'
        if answer_type == 'answered' and PARTIAL_MIN_CONFIDENCE <= confidence < PARTIAL_MAX_CONFIDENCE:
            return 'partial_answer', confidence, warning
        if answer_type == 'partial_answer' and not answer.startswith(PARTIAL_PREFIX):
            return answer_type, confidence, warning
        return answer_type, confidence, warning

    def _overview_results(self, request: RagAskRequest) -> list[RetrievedChunk]:
        try:
            rows = MySqlService(self.settings).get_chunks(request.document_id)
        except Exception as error:
            logger.warning('Overview chunk lookup failed: %s', error)
            return []
        chunks = [self._chunk_from_row(row) for row in rows if str(row.get('user_id')) == str(request.user_id)]
        if not chunks:
            return []

        title_chunks = [chunk for chunk in chunks if self._is_high_level_chunk(chunk.content)]
        first_chunks = sorted(chunks, key=lambda chunk: (chunk.page_start, chunk.chunk_index))[: self.settings.max_context_chunks]
        selected_chunks = []
        seen = set()
        for chunk in title_chunks[:2] + first_chunks:
            if chunk.chunk_id not in seen:
                seen.add(chunk.chunk_id)
                selected_chunks.append(chunk)
            if len(selected_chunks) >= self.settings.max_context_chunks:
                break

        selected_ids = {chunk.chunk_id for chunk in selected_chunks}
        results = []
        for chunk in selected_chunks:
            results.append(self._retrieved(chunk, 0.62, True, 'Selected for document overview from title/first/high-level chunks.'))
        for chunk in chunks:
            if chunk.chunk_id not in selected_ids:
                results.append(self._retrieved(chunk, 0.42, False, 'Related overview chunk not used as primary summary context.'))
            if len(results) >= self.settings.top_k:
                break
        return results

    def _overview_answer(self, request: RagAskRequest, chunks: list[Chunk]) -> str:
        file_name = chunks[0].file_name if chunks else 'uploaded document'
        question = f'Tom tat that ngan gon noi dung chinh cua tai lieu "{file_name}" trong toi da 5 y chinh. Neu chi co mot phan tai lieu, hay noi ro day la tom tat so bo.'
        return self._compact_overview(LlmService(self.settings).answer(question, chunks))

    def _chunk_from_row(self, row: dict) -> Chunk:
        return Chunk(
            chunk_id=str(row['id']),
            document_id=str(row['document_id']),
            user_id=str(row['user_id']),
            chunk_index=int(row.get('chunk_index') or 0),
            page_start=int(row.get('page_start') or 1),
            page_end=int(row.get('page_end') or row.get('page_start') or 1),
            char_start=int(row.get('char_start') or 0),
            char_end=int(row.get('char_end') or 0),
            token_count=int(row.get('token_count') or 0),
            content=row.get('content') or '',
            chunk_reason=row.get('chunk_reason') or 'overview',
            file_name=row.get('file_name') or 'uploaded_pdf',
            qdrant_point_id=row.get('qdrant_point_id'),
        )

    def _retrieved(self, chunk: Chunk, score: float, selected: bool, reason: str) -> RetrievedChunk:
        return RetrievedChunk(
            chunk=chunk,
            vector_score=score,
            keyword_score=0.0,
            final_score=score,
            selected_for_context=selected,
            reason=reason,
        )

    def _is_overview_question(self, question: str) -> bool:
        normalized = self._normalize_text(question)
        patterns = (
            'noi dung chinh',
            'tom tat',
            'tai lieu nay noi ve gi',
            'noi ve gi',
            'chu de chinh',
            'tong quan',
            'overview',
            'summary',
        )
        return any(pattern in normalized for pattern in patterns)

    def _is_high_level_chunk(self, content: str) -> bool:
        normalized = self._normalize_text(content[:1200])
        markers = (
            'muc luc',
            'table of contents',
            'chuong ',
            'chapter ',
            'phan ',
            'bai ',
            'gioi thieu',
            'tong quan',
        )
        return any(marker in normalized for marker in markers)

    def _support_level(self, final_score: float) -> str:
        if final_score >= 0.75:
            return 'strong'
        if final_score >= 0.55:
            return 'medium'
        if final_score >= self.settings.min_score:
            return 'weak'
        return 'below_threshold'

    def _source_from_result(self, result: RetrievedChunk) -> Source:
        return Source(
            chunk_id=result.chunk.chunk_id,
            file_name=result.chunk.file_name,
            page_start=result.chunk.page_start,
            page_end=result.chunk.page_end,
            score=result.final_score,
            support_level=self._support_level(result.final_score),
            preview=result.chunk.content[:320],
        )

    def _partialize(self, answer: str, answer_type: str) -> str:
        if answer_type != 'partial_answer' or answer.startswith(PARTIAL_PREFIX):
            return answer
        return PARTIAL_PREFIX + answer.strip()

    def _compact_overview(self, answer: str) -> str:
        answer = (answer or '').strip()
        if len(answer) <= 1000:
            return answer
        lines = [line.strip() for line in answer.splitlines() if line.strip()]
        bullet_lines = [line for line in lines if line.startswith(('-', '*', '•'))]
        if bullet_lines:
            compact = '\n'.join(bullet_lines[:5])
            if len(compact) <= 1000:
                return compact
        cut = max(answer.rfind('.', 0, 1000), answer.rfind(';', 0, 1000), answer.rfind('\n', 0, 1000))
        return answer[:cut + 1] if cut > 300 else answer[:1000].rsplit(' ', 1)[0] + '.'

    def _is_insufficient_answer(self, answer: str) -> bool:
        normalized = self._normalize_text(answer or '')
        refusal_markers = (
            self._normalize_text(REFUSAL),
            'khong du',
            'chua du',
            'khong cung cap du',
            'khong co du thong tin',
            'not enough',
            'insufficient',
            'do not provide enough',
            'does not provide enough',
        )
        return any(marker in normalized for marker in refusal_markers)

    def _normalize_text(self, text: str) -> str:
        text = unicodedata.normalize('NFD', text.lower())
        text = ''.join(ch for ch in text if unicodedata.category(ch) != 'Mn')
        text = text.replace('đ', 'd')
        return re.sub(r'\s+', ' ', text).strip()

    def _related_results(self, retrieved: list[RetrievedChunk], evidence_results: list[RetrievedChunk], answer_type: str) -> list[RetrievedChunk]:
        evidence_ids = {result.chunk.chunk_id for result in evidence_results}
        if answer_type in ('insufficient_context', 'out_of_scope'):
            return [result for result in retrieved[: self.settings.top_k] if result.chunk.chunk_id not in evidence_ids]
        return [
            result
            for result in retrieved[: self.settings.top_k]
            if result.chunk.chunk_id not in evidence_ids and self._support_level(result.final_score) in ('weak', 'below_threshold')
        ]

    def _write_retrieval_report(self, request: RagAskRequest, retrieved: list[RetrievedChunk], selected: list[RetrievedChunk]) -> str:
        report = {
            'message_id': request.message_id,
            'question': request.question,
            'document_id': request.document_id,
            'top_k': self.settings.top_k,
            'min_score': self.settings.min_score,
            'max_context_chunks': self.settings.max_context_chunks,
            'overview_question': self._is_overview_question(request.question),
            'retrieved_chunks': [
                {
                    'chunk_id': result.chunk.chunk_id,
                    'file_name': result.chunk.file_name,
                    'page_start': result.chunk.page_start,
                    'page_end': result.chunk.page_end,
                    'vector_score': result.vector_score,
                    'keyword_score': result.keyword_score,
                    'final_score': result.final_score,
                    'support_level': self._support_level(result.final_score),
                    'selected_for_context': result.selected_for_context,
                    'reason': result.reason,
                    'preview': result.chunk.content[:240],
                }
                for result in retrieved
            ],
            'selected_chunks': [result.chunk.chunk_id for result in selected],
            'rejected_chunks': [result.chunk.chunk_id for result in retrieved if not result.selected_for_context],
            'created_at': utc_now(),
        }
        return self.reports.write(f'retrieval_report_{request.message_id}.json', report)

    def _write_answer_report(
        self,
        request: RagAskRequest,
        retrieved: list[RetrievedChunk],
        selected: list[RetrievedChunk],
        answer: str,
        confidence: float,
        warning: str | None,
        answer_type: str,
        related: list[RetrievedChunk],
    ) -> str:
        report = {
            'message_id': request.message_id,
            'question': request.question,
            'answer': answer,
            'answer_type': answer_type,
            'confidence': confidence,
            'suggested_questions': self._suggested_questions(request, answer_type, selected or related),
            'used_chunks': [
                {
                    'chunk_id': result.chunk.chunk_id,
                    'file_name': result.chunk.file_name,
                    'page_start': result.chunk.page_start,
                    'page_end': result.chunk.page_end,
                    'supporting_text': result.chunk.content[:900],
                    'support_level': self._support_level(result.final_score),
                    'final_score': result.final_score,
                    'reason': 'This chunk was selected by final_score and used as LLM context.',
                }
                for result in selected
            ],
            'related_chunks': [
                {
                    'chunk_id': result.chunk.chunk_id,
                    'file_name': result.chunk.file_name,
                    'page_start': result.chunk.page_start,
                    'page_end': result.chunk.page_end,
                    'support_level': self._support_level(result.final_score),
                    'final_score': result.final_score,
                    'reason': 'Retrieved but not used as reliable evidence.',
                }
                for result in related
            ],
            'not_used_chunks': [{'chunk_id': result.chunk.chunk_id, 'reason': result.reason} for result in retrieved if not result.selected_for_context],
            'warning': warning,
            'created_at': utc_now(),
        }
        return self.reports.write(f'answer_report_{request.message_id}.json', report)
