from app.config import Settings
from app.models.schemas import Chunk
from app.services import retrieval_service as retrieval_module
from app.services.retrieval_service import RetrievalService


def _chunk(chunk_id: str, content: str, page: int = 1, index: int = 0) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        document_id="d",
        user_id="u",
        chunk_index=index,
        page_start=page,
        page_end=page,
        char_start=0,
        char_end=len(content),
        token_count=len(content.split()),
        content=content,
        chunk_reason="test",
        file_name="doc.pdf",
    )


class FakeQdrant:
    def search(self, user_id, document_id, question, top_k):
        return [
            (
                _chunk("c1", "Bạch Đằng năm 938 do Ngô Quyền lãnh đạo."),
                0.8,
            )
        ]


def test_retrieval_final_score_and_selection_reason():
    service = RetrievalService(Settings(MIN_SCORE=0.45, TOP_K=12, MAX_CONTEXT_CHUNKS=5), FakeQdrant())
    result = service.retrieve("u", "d", "Ai lãnh đạo chiến thắng Bạch Đằng năm 938?")
    assert result[0].keyword_score > 0.5
    assert result[0].final_score >= 0.45
    assert result[0].selected_for_context is True
    assert "Selected because final_score" in result[0].reason


class DoiMoiQdrant:
    def __init__(self):
        self.calls = []

    def search(self, user_id, document_id, question, top_k):
        self.calls.append(question)
        if question == "Vì sao Việt Nam phải tiến hành công cuộc Đổi mới từ năm 1986?":
            return [
                (
                    _chunk(
                        "caption",
                        "LỊCH SỬ VIỆT NAM - TẬP 15 Những chiếc quạt cây nhập ngoại trong 2 năm đầu của thời kỳ đổi mới. "
                        "Nguồn: Ảnh chụp năm 1988 http://example.test/anh http://example.test/source",
                        page=84,
                        index=84,
                    ),
                    0.95,
                ),
                (
                    _chunk(
                        "duplicate",
                        "Đổi mới ở Việt Nam được nhắc trong tài liệu tham khảo.",
                        page=433,
                        index=433,
                    ),
                    0.5,
                ),
            ]
        if "Đại hội VI" in question or "khủng hoảng kinh tế xã hội" in question:
            return [
                (
                    _chunk(
                        "dai-hoi-vi",
                        "Đại hội VI nhìn thẳng vào sự thật, chỉ ra sai lầm khuyết điểm: chưa đánh giá đúng tình hình, "
                        "nóng vội công nghiệp hóa, chỉ tiêu kế hoạch quá cao, cơ chế quản lý kinh tế quan liêu bao cấp.",
                        page=38,
                        index=38,
                    ),
                    0.74,
                ),
                (
                    _chunk(
                        "duplicate",
                        "Đại hội VI nêu yêu cầu đổi mới cơ chế quản lý kinh tế.",
                        page=39,
                        index=39,
                    ),
                    0.82,
                ),
            ]
        return []


def test_multi_query_retrieval_deduplicates_penalizes_and_ranks_reason_chunks():
    qdrant = DoiMoiQdrant()
    service = RetrievalService(Settings(MIN_SCORE=0.45, TOP_K=12, MAX_CONTEXT_CHUNKS=5), qdrant)

    result = service.retrieve("u", "d", "Vì sao Việt Nam phải tiến hành công cuộc Đổi mới từ năm 1986?")

    assert len(qdrant.calls) > 1
    assert len({item.chunk.chunk_id for item in result}) == len(result)
    assert result[0].chunk.chunk_id == "dai-hoi-vi"
    assert result[0].selected_for_context is True
    assert result[0].retrieval_query and result[0].retrieval_query != qdrant.calls[0]

    caption = next(item for item in result if item.chunk.chunk_id == "caption")
    assert caption.quality_penalty > 0
    assert caption.final_score < result[0].final_score


class EmptyIdQdrant:
    def search(self, user_id, document_id, question, top_k):
        return [
            (_chunk("", "Đại hội VI nêu đổi mới cơ chế quản lý kinh tế.", page=38, index=7), 0.7),
            (_chunk("", "Đại hội VI nêu đổi mới cơ chế quản lý kinh tế.", page=38, index=7), 0.9),
        ]


def test_deduplicates_by_document_page_and_chunk_index_when_chunk_id_missing():
    service = RetrievalService(Settings(MIN_SCORE=0.45, TOP_K=12, MAX_CONTEXT_CHUNKS=5), EmptyIdQdrant())

    result = service.retrieve("u", "d", "Đại hội VI có ý nghĩa gì?")

    assert len(result) == 1
    assert result[0].vector_score == 0.9


class VectorMissesImportantChunkQdrant:
    def search(self, user_id, document_id, question, top_k):
        return [
            (
                _chunk(
                    "caption-only",
                    "Phụ lục ảnh về thời kỳ Đổi mới. Nguồn: http://example.test/a http://example.test/b",
                    page=84,
                    index=80,
                ),
                0.9,
            )
        ]


def test_mysql_lexical_candidates_are_blended_even_when_vector_hits_exist(monkeypatch):
    rows = [
        {
            "id": "dai-hoi-vi-mysql",
            "document_id": "d",
            "user_id": "u",
            "chunk_index": 38,
            "page_start": 38,
            "page_end": 38,
            "char_start": 0,
            "char_end": 200,
            "token_count": 40,
            "content": (
                "Đại hội đại biểu toàn quốc lần thứ VI chỉ rõ sai lầm khuyết điểm, "
                "kế hoạch 5 năm 1976-1980, cơ chế quản lý kinh tế quan liêu bao cấp."
            ),
            "chunk_reason": "test",
            "file_name": "lich-su.pdf",
            "qdrant_point_id": None,
        }
    ]
    monkeypatch.setattr(retrieval_module.MySqlService, "get_chunks", lambda self, document_id: rows)
    service = RetrievalService(Settings(MIN_SCORE=0.45, TOP_K=12, MAX_CONTEXT_CHUNKS=5), VectorMissesImportantChunkQdrant())

    result = service.retrieve("u", "d", "Vì sao Việt Nam phải tiến hành công cuộc Đổi mới từ năm 1986?")

    assert result[0].chunk.chunk_id == "dai-hoi-vi-mysql"
    assert result[0].selected_for_context is True
    assert result[0].retrieval_query
