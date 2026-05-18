from app.core.config import Settings
from app.core.logging import get_logger
from app.infrastructure.qdrant.qdrant_service import QdrantService
from app.models.schemas import RagAskRequest, RagAskResponse, Source, utc_now
from app.services.embedding.embedding_service import EmbeddingService
from app.services.llm.llm_service import LlmService, REFUSAL
from app.services.reports.chunk_report_service import ChunkReportService
from app.services.retrieval.retrieval_service import RetrievalService
from app.services.retrieval.reranking_service import RerankingService

logger = get_logger(__name__)


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
        retrieval = RetrievalService(self.settings, QdrantService(self.settings, EmbeddingService(self.settings)))
        retrieved = retrieval.retrieve(request.user_id, request.document_id, request.question)
        retrieved = RerankingService().rerank(retrieved)
        selected = [result for result in retrieved if result.selected_for_context][: self.settings.max_context_chunks]
        selected_chunks = [result.chunk for result in selected]

        if not selected_chunks:
            if not retrieved:
                answer = 'Tài liệu hiện tại chưa có đoạn nội dung nào có thể dùng để trả lời. Vui lòng kiểm tra lại quá trình ingest/OCR của tài liệu.'
                confidence = 0.0
                warning = 'No chunks were retrieved. The document may have zero chunks, scan-only content, or ingestion failed.'
            else:
                answer = REFUSAL
                confidence = 0.25
                warning = 'No chunk met MIN_SCORE; refusing to answer to avoid hallucination.'
        else:
            answer = LlmService(self.settings).answer(request.question, selected_chunks)
            confidence = round(sum(result.final_score for result in selected) / len(selected), 4)
            warning = None

        retrieval_path = self._write_retrieval_report(request, retrieved, selected)
        answer_path = self._write_answer_report(request, retrieved, selected, answer, confidence, warning)
        sources = [
            Source(
                chunk_id=result.chunk.chunk_id,
                file_name=result.chunk.file_name,
                page_start=result.chunk.page_start,
                page_end=result.chunk.page_end,
                score=result.final_score,
                support_level='strong' if result.keyword_score > 0 else 'medium',
                preview=result.chunk.content[:320],
            )
            for result in selected
        ]
        logger.info(
            'rag ask complete message_id=%s retrieved=%s selected=%s confidence=%s',
            request.message_id,
            len(retrieved),
            len(selected),
            confidence,
        )
        return RagAskResponse(
            answer=answer,
            confidence=confidence,
            sources=sources,
            warning=warning,
            retrieval_report_path=retrieval_path,
            answer_report_path=answer_path,
        )

    def _write_retrieval_report(self, request: RagAskRequest, retrieved: list, selected: list) -> str:
        report = {
            'message_id': request.message_id,
            'question': request.question,
            'document_id': request.document_id,
            'top_k': self.settings.top_k,
            'min_score': self.settings.min_score,
            'max_context_chunks': self.settings.max_context_chunks,
            'retrieved_chunks': [
                {
                    'chunk_id': result.chunk.chunk_id,
                    'file_name': result.chunk.file_name,
                    'page_start': result.chunk.page_start,
                    'page_end': result.chunk.page_end,
                    'vector_score': result.vector_score,
                    'keyword_score': result.keyword_score,
                    'final_score': result.final_score,
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

    def _write_answer_report(self, request: RagAskRequest, retrieved: list, selected: list, answer: str, confidence: float, warning: str | None) -> str:
        report = {
            'message_id': request.message_id,
            'question': request.question,
            'answer': answer,
            'confidence': confidence,
            'used_chunks': [
                {
                    'chunk_id': result.chunk.chunk_id,
                    'file_name': result.chunk.file_name,
                    'page_start': result.chunk.page_start,
                    'page_end': result.chunk.page_end,
                    'supporting_text': result.chunk.content[:900],
                    'support_level': 'strong' if result.keyword_score > 0 else 'medium',
                    'reason': 'This chunk was selected by final_score and used as LLM context.',
                }
                for result in selected
            ],
            'not_used_chunks': [{'chunk_id': result.chunk.chunk_id, 'reason': result.reason} for result in retrieved if not result.selected_for_context],
            'warning': warning,
            'created_at': utc_now(),
        }
        return self.reports.write(f'answer_report_{request.message_id}.json', report)
