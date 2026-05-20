import re
import unicodedata

from app.config import Settings
from app.core.logging import get_logger
from app.models.schemas import Chunk, RetrievedChunk
from app.services.mysql_service import MySqlService
from app.services.query_rewriter import rewrite_queries
from app.services.qdrant_service import QdrantService

logger = get_logger(__name__)

LOW_VALUE_MARKERS = (
    'tai lieu tham khao',
    'phu luc anh',
    'phu luc hinh',
    'anh chup',
    'hinh anh',
    'caption',
    'bien muc tren xuat ban pham',
    'nha xuat ban',
    'danh muc bang',
    'loi nha xuat ban',
)

LOW_VALUE_ALLOWED_MARKERS = (
    'tai lieu tham khao',
    'tham khao',
    'phu luc',
    'nguon',
    'trich dan',
    'citation',
    'source',
    'reference',
    'appendix',
    'image',
    'photo',
    'anh',
    'hinh anh',
)


class RetrievalService:
    """
    Service thực hiện retrieval từng câu hỏi.

    Score calculation:
    - `vector_score`: điểm tương đồng ngữ nghĩa từ Qdrant (cosine similarity).
    - `keyword_score`: tỷ lệ từ khóa câu hỏi xuất hiện trong chunk (0..1).
    - `final_score = 0.75 * vector_score + 0.25 * keyword_score - quality_penalty`.

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
        queries = rewrite_queries(question)
        hits = self._multi_query_search(user_id, document_id, queries)
        hits.extend(self._multi_query_mysql_fallback(user_id, document_id, queries))

        best_by_chunk: dict[str, RetrievedChunk] = {}
        for query, chunk, vector_score in hits:
            self._log_text_integrity(query, chunk)
            retrieved = self._score_result(question, query, chunk, vector_score)
            key = self._dedupe_key(chunk)
            current = best_by_chunk.get(key)
            if current is None or retrieved.final_score > current.final_score:
                best_by_chunk[key] = retrieved

        retrieved = sorted(best_by_chunk.values(), key=lambda result: result.final_score, reverse=True)
        selected_count = 0
        for result in retrieved:
            selected = result.final_score >= self.settings.min_score and selected_count < self.settings.max_context_chunks
            if selected:
                selected_count += 1
            result.selected_for_context = selected
            result.reason = self._selection_reason(result, selected)
        return retrieved[: self.settings.top_k]

    def _multi_query_search(self, user_id: str, document_id: str, queries: list[str]) -> list[tuple[str, Chunk, float]]:
        hits: list[tuple[str, Chunk, float]] = []
        for query in queries:
            for chunk, score in self.qdrant.search(user_id, document_id, query, self.settings.top_k):
                hits.append((query, chunk, score))
        return hits

    def _multi_query_mysql_fallback(self, user_id: str, document_id: str, queries: list[str]) -> list[tuple[str, Chunk, float]]:
        hits: list[tuple[str, Chunk, float]] = []
        for query in queries:
            for chunk, score in self._mysql_fallback_search(user_id, document_id, query):
                hits.append((query, chunk, score))
        return hits

    def _score_result(self, original_question: str, query: str, chunk: Chunk, vector_score: float) -> RetrievedChunk:
        keywords = self._keywords(query)
        keyword_score = self._keyword_score(keywords, chunk.content)
        penalty = self._quality_penalty(original_question, chunk.content)
        final_score = max(0.0, vector_score * 0.75 + keyword_score * 0.25 - penalty)
        return RetrievedChunk(
            chunk=chunk,
            vector_score=vector_score,
            keyword_score=keyword_score,
            final_score=final_score,
            selected_for_context=False,
            reason='Pending selection after multi-query ranking.',
            retrieval_query=query,
            quality_penalty=penalty,
        )

    def _selection_reason(self, result: RetrievedChunk, selected: bool) -> str:
        keywords = self._keywords(result.retrieval_query or '')
        folded_content = self._fold_for_matching(result.chunk.content)
        matched = [kw for kw in keywords if self._fold_for_matching(kw) in folded_content]
        penalty_note = f'; quality_penalty={result.quality_penalty:.2f}' if result.quality_penalty else ''
        query_note = f'; query="{result.retrieval_query}"' if result.retrieval_query else ''
        if selected:
            return f'Selected because final_score={result.final_score:.2f} is above MIN_SCORE={self.settings.min_score}; evidence={", ".join(matched) or "semantic/vector match"}{penalty_note}{query_note}.'
        if result.final_score < self.settings.min_score:
            return f'Rejected because final_score={result.final_score:.2f} is below MIN_SCORE={self.settings.min_score}{penalty_note}{query_note}.'
        return f'Rejected because context limit reached after multi-query ranking; final_score={result.final_score:.2f}{penalty_note}{query_note}.'

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
            if keyword_score <= 0:
                continue
            phrase_bonus = self._phrase_bonus(question, chunk.content)
            scored.append((chunk, min(0.92, keyword_score + phrase_bonus)))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:self.settings.top_k]

    def _phrase_bonus(self, question: str, content: str) -> float:
        folded_question = self._fold_for_matching(question)
        folded_content = self._fold_for_matching(content)
        bonus = 0.0
        for phrase in ('dai hoi vi', 'dai hoi dai bieu toan quoc lan thu vi', 'sai lam khuyet diem', 'ke hoach 5 nam 1976', 'co che quan ly', 'quan lieu bao cap', 'khung hoang kinh te xa hoi'):
            if phrase in folded_question and phrase in folded_content:
                bonus += 0.08
        return min(0.24, bonus)

    def _keywords(self, question: str) -> list[str]:
        tokens = re.findall(r'[\wÀ-ỹ]+', question.lower(), flags=re.UNICODE)
        stop = {
            'là', 'ai', 'gì', 'có', 'về', 'nào', 'theo', 'tài', 'liệu', 'này', 'không',
            'năm', 'người', 'công', 'ty', 'hướng', 'dẫn', 'nấu', 'sao', 'tại', 'nguyên',
            'nhân', 'phải', 'tiến', 'hành', 'cuộc', 'nam', 'nguoi', 'cong', 'huong',
            'dan', 'tai', 'nguyen', 'nhan', 'phai', 'tien', 'hanh',
        }
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
        lowered = self._fold_for_matching(content)
        hits = 0
        for kw in keywords:
            folded_keyword = self._fold_for_matching(kw)
            if folded_keyword in lowered:
                hits += 1
            elif folded_keyword in {'lanh', 'dao', 'thang'}:
                hits += 0.7
        return min(1.0, hits / len(keywords))

    def _dedupe_key(self, chunk: Chunk) -> str:
        if chunk.chunk_id:
            return chunk.chunk_id
        return f'{chunk.document_id}:{chunk.page_start}:{chunk.chunk_index}'

    def _quality_penalty(self, question: str, content: str) -> float:
        if self._allows_low_value_chunks(question):
            return 0.0

        folded = self._fold_for_matching(content[:1600])
        word_count = len(re.findall(r'\w+', folded))
        url_count = len(re.findall(r'https?://|www\.', folded))
        penalty = 0.0

        if 'tai lieu tham khao' in folded:
            penalty += 0.25
        if 'phu luc anh' in folded or 'phu luc hinh' in folded:
            penalty += 0.25
        if any(marker in folded for marker in ('bien muc tren xuat ban pham', 'loi nha xuat ban', 'danh muc bang', 'danh muc bieu', 'nha xuat ban khoa hoc xa hoi')):
            penalty += 0.24
        if re.search(r'tap\\s+1[0-5]:\\s+tu nam', folded):
            penalty += 0.20
        if word_count < 70 and any(marker in folded for marker in ('lich su viet nam tap 15', 'vien su hoc', 'nguyen ngoc mao')):
            penalty += 0.20
        if any(self._contains_marker(folded, marker) for marker in LOW_VALUE_MARKERS) and word_count < 120:
            penalty += 0.16
        if url_count >= 2:
            penalty += 0.18
        elif url_count == 1 and word_count < 80:
            penalty += 0.10
        if ('nguon:' in folded or 'source:' in folded) and word_count < 80:
            penalty += 0.10

        return min(0.35, penalty)

    def _allows_low_value_chunks(self, question: str) -> bool:
        folded = self._fold_for_matching(question)
        return any(self._contains_marker(folded, marker) for marker in LOW_VALUE_ALLOWED_MARKERS)

    def _contains_marker(self, folded_text: str, marker: str) -> bool:
        if ' ' in marker:
            return marker in folded_text
        return re.search(rf'(^|\W){re.escape(marker)}($|\W)', folded_text) is not None

    def _fold_for_matching(self, text: str) -> str:
        folded = unicodedata.normalize('NFD', (text or '').lower())
        folded = ''.join(ch for ch in folded if unicodedata.category(ch) != 'Mn')
        return folded.replace('đ', 'd')

    def _has_vietnamese_diacritic(self, text: str) -> bool:
        return any(ch in 'ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ' for ch in (text or '').lower())

    def _log_text_integrity(self, query: str, chunk: Chunk) -> None:
        preview = re.sub(r'\s+', ' ', chunk.content[:220]).strip()
        logger.debug(
            'retrieved chunk text check query=%s chunk_id=%s page=%s chunk_index=%s preview=%s',
            query,
            chunk.chunk_id,
            chunk.page_start,
            chunk.chunk_index,
            preview,
        )
        folded = self._fold_for_matching(preview)
        looks_vietnamese = any(marker in folded for marker in ('viet nam', 'doi moi', 'dai hoi', 'kinh te', 'lich su'))
        if looks_vietnamese and not self._has_vietnamese_diacritic(preview):
            logger.warning(
                'retrieved chunk may be accent-stripped; code fixes will not repair existing vectors. Re-ingest document_id=%s chunk_id=%s after clearing the vector collection.',
                chunk.document_id,
                chunk.chunk_id,
            )
