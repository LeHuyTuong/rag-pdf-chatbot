from app.config import Settings
from app.models.schemas import Chunk
from app.services.llm_service import LlmService, REFUSAL


def test_fallback_who_answer_is_concise_not_repeated():
    chunk = Chunk(
        chunk_id="c1",
        document_id="d",
        user_id="u",
        chunk_index=0,
        page_start=1,
        page_end=1,
        char_start=0,
        char_end=10,
        token_count=20,
        content=(
            "Chiến thắng Bạch Đằng năm 938 do Ngô Quyền lãnh đạo. "
            "Ngô Quyền cho đóng cọc trên sông Bạch Đằng."
        ),
        chunk_reason="test",
        file_name="doc.pdf",
    )
    settings = Settings(OPENAI_API_KEY=None, LLM_API_KEY=None, LLM_BASE_URL=None, LLM_PROVIDER="none")
    answer = LlmService(settings).answer("Ai lãnh đạo chiến thắng Bạch Đằng năm 938?", [chunk])
    assert answer.startswith("Chiến thắng Bạch Đằng năm 938 do Ngô Quyền lãnh đạo.")
    assert answer.count("Chiến thắng Bạch Đằng") == 1
    assert "Nguồn tham khảo" in answer


def test_fallback_refuses_without_context():
    settings = Settings(OPENAI_API_KEY=None, LLM_API_KEY=None, LLM_BASE_URL=None, LLM_PROVIDER="none")
    assert LlmService(settings).answer("Tài liệu nói về blockchain không?", []) == REFUSAL
