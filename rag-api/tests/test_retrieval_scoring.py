from app.config import Settings
from app.models.schemas import Chunk
from app.services.retrieval_service import RetrievalService


class FakeQdrant:
    def search(self, user_id, document_id, question, top_k):
        return [
            (
                Chunk(
                    chunk_id="c1",
                    document_id=document_id,
                    user_id=user_id,
                    chunk_index=0,
                    page_start=1,
                    page_end=1,
                    char_start=0,
                    char_end=10,
                    token_count=10,
                    content="Bạch Đằng năm 938 do Ngô Quyền lãnh đạo.",
                    chunk_reason="test",
                    file_name="doc.pdf",
                ),
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
