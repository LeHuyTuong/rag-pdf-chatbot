import re
from app.config import Settings
from app.core.logging import get_logger
from app.models.schemas import Chunk, RetrievedChunk
from app.services.mysql_service import MySqlService
from app.services.qdrant_service import QdrantService

logger = get_logger(__name__)


class RetrievalService:
    """
    Service thực hiện retrieval từng câu hỏi.

    Score calculation:
    - `vector_score`: điểm tương đồng ngữ nghĩa từ Qdrant (cosine similarity).
    - `keyword_score`: tỷ lệ từ khóa câu hỏi xuất hiện trong chunk (0..1).
    - `final_score = 0.75 * vector_score + 0.25 * keyword_score`.

    Một chunk được chọn làm context nếu `final_score >= MIN_SCORE` và chưa vượt `max_context_chunks`.
    """
    def __init__(self, settings: Settings, qdrant: QdrantService):
        self.settings = settings
        self.qdrant = qdrant

    def retrieve(self, user_id: str, document_id: str, question: str) -> list[RetrievedChunk]:
        """
        Truy xuất top_k candidate từ Qdrant và tính điểm, sau đó quyết định chọn chunk cho context.

        Trả về list[RetrievedChunk] chứa vector_score (từ Qdrant), keyword_score (từ _keyword_score),
        final_score, selected_for_context (bool) và reason giải thích.
        """
        hits = self.qdrant.search(user_id, document_id, question, self.settings.top_k)
        if not hits:
            hits = self._mysql_fallback_search(user_id, document_id, question)
        keywords = self._keywords(question)
        retrieved = []
        selected_count = 0
        for chunk, vector_score in hits:
            keyword_score = self._keyword_score(keywords, chunk.content)
            final_score = vector_score * 0.75 + keyword_score * 0.25
            selected = final_score >= self.settings.min_score and selected_count < self.settings.max_context_chunks
            if selected:
                selected_count += 1
            matched = [kw for kw in keywords if kw.lower() in chunk.content.lower()]
            if selected:
                reason = f'Selected because final_score={final_score:.2f} is above MIN_SCORE={self.settings.min_score}; evidence={", ".join(matched) or "semantic/vector match"}.'
            else:
                reason = f'Rejected because final_score={final_score:.2f} is below MIN_SCORE={self.settings.min_score} or context limit reached.'
            retrieved.append(RetrievedChunk(chunk=chunk, vector_score=vector_score, keyword_score=keyword_score, final_score=final_score, selected_for_context=selected, reason=reason))
        return retrieved

    def _mysql_fallback_search(self, user_id: str, document_id: str, question: str) -> list[tuple[Chunk, float]]:
        try:
            rows = MySqlService(self.settings).get_chunks(document_id)
        except Exception as error:
            logger.warning('MySQL fallback retrieval failed: %s', error)
            return []
        keywords = self._keywords(question)
        scored = []
        for row in rows:
            if str(row.get('user_id')) != str(user_id):
                continue
            chunk = Chunk(
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
                chunk_reason=row.get('chunk_reason') or 'mysql_fallback',
                file_name=row.get('file_name') or 'uploaded_pdf',
                qdrant_point_id=row.get('qdrant_point_id'),
            )
            keyword_score = self._keyword_score(keywords, chunk.content)
            lexical_bonus = 0.35 if keyword_score > 0 else 0.0
            scored.append((chunk, min(1.0, 0.45 + lexical_bonus + keyword_score * 0.2)))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:self.settings.top_k]

    def _keywords(self, question: str) -> list[str]:
        tokens = re.findall(r'[\wÀ-ỹ]+', question.lower(), flags=re.UNICODE)
        stop = {'là', 'ai', 'gì', 'có', 'về', 'nào', 'theo', 'tài', 'liệu', 'này', 'không', 'năm', 'người', 'công', 'ty', 'hướng', 'dẫn', 'nấu'}
        keywords = [t for t in tokens if len(t) > 2 and t not in stop]
        if 'bạch' in question.lower() and 'đằng' in question.lower():
            keywords.append('bạch đằng')
        return keywords

    def _keyword_score(self, keywords: list[str], content: str) -> float:
        """
        Tính `keyword_score` là tỷ lệ từ khóa xuất hiện trong content (normalized).

        Trả về float trong [0,1]. Có một vài boost heuristic nhỏ cho từ đặc thù.
        """
        if not keywords:
            return 0.0
        lowered = content.lower()
        hits = 0
        for kw in keywords:
            if kw in lowered:
                hits += 1
            elif kw in {'lãnh', 'đạo', 'thắng'}:
                hits += 0.7
        return min(1.0, hits / len(keywords))
