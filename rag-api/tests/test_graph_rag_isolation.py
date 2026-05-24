from app.config import Settings
from app.models.schemas import RagAskRequest
from app.pipelines.rag_pipeline import NO_CHUNKS_ANSWER, RagPipeline


def test_dinh_bo_linh_question_refuses_when_existing_rag_has_no_evidence():
    settings = Settings(LLM_PROVIDER='none', OPENAI_API_KEY=None, LLM_API_KEY=None)
    request = RagAskRequest(
        user_id='user',
        document_id='document',
        session_id='session',
        message_id='message',
        question='Ai la \u0110inh B\u1ed9 L\u0129nh?',
    )

    answer, confidence, answer_type, warning = RagPipeline(settings)._build_answer(request, [], [])

    assert answer == NO_CHUNKS_ANSWER
    assert answer_type == 'insufficient_context'
    assert confidence == 0.0
    assert 'No chunks were retrieved' in warning
