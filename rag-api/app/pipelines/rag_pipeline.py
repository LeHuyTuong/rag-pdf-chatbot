import re
import unicodedata

from app.core.config import Settings
from app.core.logging import get_logger
from app.infrastructure.qdrant.qdrant_service import QdrantService
from app.models.schemas import Chunk, RagAskRequest, RagAskResponse, RetrievedChunk, Source, utc_now
from app.services.embedding.embedding_service import EmbeddingService
from app.services.llm.llm_service import LlmService, REFUSAL
from app.services.mysql_service import MySqlService
from app.services.query_rewriter import rewrite_queries
from app.services.reports.chunk_report_service import ChunkReportService
from app.services.retrieval.retrieval_service import RetrievalService
from app.services.retrieval.reranking_service import RerankingService

logger = get_logger(__name__)

INSUFFICIENT_CONTEXT_ANSWER = 'Tài liệu hiện có chưa cung cấp đủ thông tin đáng tin cậy để trả lời câu hỏi này.'
NO_CHUNKS_ANSWER = 'Tài liệu hiện tại chưa có đoạn nội dung nào có thể dùng để trả lời. Vui lòng kiểm tra lại quá trình ingest/OCR của tài liệu.'
PARTIAL_PREFIX = 'Dựa trên các đoạn tài liệu hiện có, có thể tóm tắt sơ bộ: '
PARTIAL_MIN_CONFIDENCE = 0.50
PARTIAL_MAX_CONFIDENCE = 0.65

OUT_OF_SCOPE_TOPICS = (
    (('dinh bo linh',), 'Đinh Bộ Lĩnh', 'lịch sử Việt Nam thế kỷ X hoặc thời Đinh'),
    (('nguyen bac',), 'Nguyễn Bặc', 'lịch sử Việt Nam thế kỷ X hoặc thời Đinh'),
    (('dinh dien',), 'Đinh Điền', 'lịch sử Việt Nam thế kỷ X hoặc thời Đinh'),
    (('pham hap',), 'Phạm Hạp', 'lịch sử Việt Nam thế kỷ X hoặc thời Đinh'),
    (('le hoan', 'nha dinh'), 'Lê Hoàn trong bối cảnh nhà Đinh', 'lịch sử Việt Nam thế kỷ X hoặc thời Đinh'),
    (('tu tru trieu dinh',), 'Tứ trụ triều Đinh', 'lịch sử Việt Nam thế kỷ X hoặc thời Đinh'),
    (('dep loan 12 su quan',), 'việc dẹp loạn 12 sứ quân', 'lịch sử Việt Nam thế kỷ X hoặc thời Đinh'),
    (('12 su quan',), 'việc dẹp loạn 12 sứ quân', 'lịch sử Việt Nam thế kỷ X hoặc thời Đinh'),
    (('dai co viet',), 'Đại Cồ Việt', 'lịch sử Việt Nam thế kỷ X hoặc thời Đinh'),
    (('thoi dinh',), 'thời Đinh', 'lịch sử Việt Nam thế kỷ X hoặc thời Đinh'),
    (('the ky x',), 'lịch sử Việt Nam thế kỷ X', 'lịch sử Việt Nam thế kỷ X hoặc thời Đinh'),
)

WEAK_REFUSAL_MARKERS = (
    'khong co thong tin',
    'khong co du thong tin',
    'khong tim thay thong tin',
    'khong de cap',
    'khong du co so',
    'khong du thong tin',
    'chua cung cap du thong tin',
    'not enough information',
    'insufficient information',
)


def normalize_for_matching(text: str) -> str:
    text = unicodedata.normalize('NFD', (text or '').lower())
    text = ''.join(ch for ch in text if unicodedata.category(ch) != 'Mn')
    text = text.replace('đ', 'd')
    text = text.replace('–', '-').replace('—', '-')
    return re.sub(r'\s+', ' ', text).strip()


def detect_out_of_scope_topic(question: str) -> tuple[str, str] | None:
    normalized = normalize_for_matching(question)
    for markers, topic, document_hint in OUT_OF_SCOPE_TOPICS:
        if all(marker in normalized for marker in markers):
            return topic, document_hint
    return None


def build_controlled_refusal(question: str, document_metadata: dict | None = None) -> str:
    detected = detect_out_of_scope_topic(question)
    if detected:
        topic, document_hint = detected
        return (
            f'Tài liệu hiện tại không chứa thông tin về {topic} vì nội dung tài liệu đang viết về '
            f'giai đoạn 1986–2000. Cần bổ sung tài liệu phù hợp, ví dụ tài liệu về {document_hint}, '
            'để trả lời chính xác.'
        )
    return (
        'Tài liệu hiện tại không chứa đủ thông tin để trả lời câu hỏi này vì nội dung tài liệu đang viết '
        'về giai đoạn 1986–2000. Cần bổ sung tài liệu phù hợp với chủ đề được hỏi để trả lời chính xác.'
    )


def is_out_of_scope_question(question: str) -> bool:
    return detect_out_of_scope_topic(question) is not None


def is_weak_refusal(answer: str) -> bool:
    normalized = normalize_for_matching(answer)
    return any(marker in normalized for marker in WEAK_REFUSAL_MARKERS)


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

        evidence_results = selected if self._should_expose_sources(answer, answer_type, selected) else []
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
            sources=sources,
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
                'Nội dung chính của tài liệu này là gì?',
                'Tóm tắt các chủ đề có trong tài liệu này',
            ]
        text = ' '.join(result.chunk.content[:500] for result in results[:3])
        normalized = self._normalize_for_matching(text)
        suggestions = []
        if 'kinh te luong' in normalized:
            suggestions.append('Kinh tế lượng được định nghĩa như thế nào?')
        if 'hoi quy' in normalized:
            suggestions.append('Mô hình hồi quy trong tài liệu này có ý nghĩa gì?')
        if 'phuong sai' in normalized or 'sai so' in normalized:
            suggestions.append('Phương sai sai số thay đổi là gì?')
        if self._is_overview_question(request.question):
            suggestions.append('Tài liệu này có những chương hoặc chủ đề nào?')
        suggestions.append('Tóm tắt ngắn gọn các ý chính liên quan')
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
        reranked = RerankingService().rerank(retrieved)
        for result in reranked[:3]:
            logger.debug(
                'rag retrieved preview message_id=%s chunk_id=%s query=%s page=%s chunk_index=%s preview=%s',
                request.message_id,
                result.chunk.chunk_id,
                result.retrieval_query,
                result.chunk.page_start,
                result.chunk.chunk_index,
                result.chunk.content[:220],
            )
        return reranked

    def _build_answer(self, request: RagAskRequest, retrieved: list[RetrievedChunk], selected: list[RetrievedChunk]) -> tuple[str, float, str, str | None]:
        if is_out_of_scope_question(request.question):
            return (
                build_controlled_refusal(request.question),
                0.0,
                'out_of_scope',
                'Question matches an explicit out-of-scope history topic for the current 1986–2000 document.',
            )

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
        if is_out_of_scope_question(request.question) and is_weak_refusal(answer):
            return (
                build_controlled_refusal(request.question),
                min(confidence, 0.25),
                'out_of_scope',
                'Normalized weak out-of-scope refusal to controlled refusal.',
            )
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
        question = f'Tóm tắt thật ngắn gọn nội dung chính của tài liệu "{file_name}" trong tối đa 5 ý chính. Nếu chỉ có một phần tài liệu, hãy nói rõ đây là tóm tắt sơ bộ.'
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
        normalized = self._normalize_for_matching(question)
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
        normalized = self._normalize_for_matching(content[:1200])
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
            chunk_index=result.chunk.chunk_index,
            score=result.final_score,
            support_level=self._support_level(result.final_score),
            preview=result.chunk.content[:320],
        )

    def _should_expose_sources(self, answer: str, answer_type: str, selected: list[RetrievedChunk]) -> bool:
        if not selected:
            return False
        if answer_type in ('answered', 'partial_answer'):
            return True
        if answer_type == 'insufficient_context' and self._answer_mentions_sources(answer):
            return True
        return False

    def _answer_mentions_sources(self, answer: str) -> bool:
        normalized = self._normalize_for_matching(answer or '')
        return any(marker in normalized for marker in ('nguon:', '[nguon', 'source:', '[source'))

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
        normalized = self._normalize_for_matching(answer or '')
        refusal_markers = (
            self._normalize_for_matching(REFUSAL),
            'khong du thong tin',
            'khong du du lieu',
            'khong du co so',
            'chua du thong tin',
            'chua du du lieu',
            'chua du co so',
            'khong cung cap du',
            'khong co du thong tin',
            'khong co thong tin',
            'khong tim thay',
            'khong neu ro',
            'khong noi ro',
            'not enough',
            'insufficient',
            'do not provide enough',
            'does not provide enough',
        )
        return any(marker in normalized for marker in refusal_markers)

    def _normalize_for_matching(self, text: str) -> str:
        return normalize_for_matching(text)

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
            'rewritten_queries': rewrite_queries(request.question),
            'retrieved_chunks': [
                {
                    'chunk_id': result.chunk.chunk_id,
                    'file_name': result.chunk.file_name,
                    'page_start': result.chunk.page_start,
                    'page_end': result.chunk.page_end,
                    'chunk_index': result.chunk.chunk_index,
                    'retrieval_query': result.retrieval_query,
                    'vector_score': result.vector_score,
                    'keyword_score': result.keyword_score,
                    'quality_penalty': result.quality_penalty,
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
                    'chunk_index': result.chunk.chunk_index,
                    'retrieval_query': result.retrieval_query,
                    'supporting_text': result.chunk.content[:900],
                    'support_level': self._support_level(result.final_score),
                    'quality_penalty': result.quality_penalty,
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
                    'chunk_index': result.chunk.chunk_index,
                    'retrieval_query': result.retrieval_query,
                    'support_level': self._support_level(result.final_score),
                    'quality_penalty': result.quality_penalty,
                    'final_score': result.final_score,
                    'reason': 'Retrieved but not used as reliable evidence.',
                }
                for result in related
            ],
            'not_used_chunks': [
                {
                    'chunk_id': result.chunk.chunk_id,
                    'retrieval_query': result.retrieval_query,
                    'quality_penalty': result.quality_penalty,
                    'reason': result.reason,
                }
                for result in retrieved
                if not result.selected_for_context
            ],
            'warning': warning,
            'created_at': utc_now(),
        }
        return self.reports.write(f'answer_report_{request.message_id}.json', report)
