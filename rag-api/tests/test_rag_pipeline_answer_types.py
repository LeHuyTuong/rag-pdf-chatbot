from pathlib import Path

from app.config import Settings
from app.models.schemas import Chunk, RagAskRequest, RetrievedChunk
from app.pipelines import rag_pipeline as pipeline_module
from app.pipelines.rag_pipeline import PARTIAL_PREFIX, RagPipeline, build_controlled_refusal


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        DEBUG_REPORT_PATH=str(tmp_path),
        MIN_SCORE=0.50,
        MAX_CONTEXT_CHUNKS=3,
        TOP_K=12,
        FAST_TEST_MODE=True,
    )


def _request(question: str = 'Noi dung chinh cua tai lieu nay la gi?') -> RagAskRequest:
    return RagAskRequest(
        user_id='user-1',
        document_id='doc-1',
        session_id='session-1',
        message_id='message-1',
        question=question,
    )


def _chunk(index: int, content: str) -> Chunk:
    return Chunk(
        chunk_id=f'chunk-{index}',
        document_id='doc-1',
        user_id='user-1',
        chunk_index=index,
        page_start=index + 1,
        page_end=index + 1,
        char_start=0,
        char_end=len(content),
        token_count=20,
        content=content,
        chunk_reason='test',
        file_name='econometrics.pdf',
    )


def test_overview_question_returns_partial_answer_with_sources(monkeypatch, tmp_path: Path):
    rows = [
        {
            'id': 'chunk-0',
            'document_id': 'doc-1',
            'user_id': 'user-1',
            'chunk_index': 0,
            'page_start': 1,
            'page_end': 1,
            'content': 'Chuong 1. Gioi thieu kinh te luong va cac dang du lieu.',
            'file_name': 'econometrics.pdf',
        },
        {
            'id': 'chunk-1',
            'document_id': 'doc-1',
            'user_id': 'user-1',
            'chunk_index': 1,
            'page_start': 2,
            'page_end': 2,
            'content': 'Tai lieu trinh bay hoi quy, du lieu chuoi thoi gian va phuong sai sai so thay doi.',
            'file_name': 'econometrics.pdf',
        },
    ]

    monkeypatch.setattr(pipeline_module.MySqlService, 'get_chunks', lambda self, document_id: rows)
    monkeypatch.setattr(pipeline_module.LlmService, 'answer', lambda self, question, chunks: 'Tai lieu gioi thieu cac chu de co ban cua kinh te luong.')

    response = RagPipeline(_settings(tmp_path)).ask(_request())

    assert response.answer_type in {'partial_answer', 'answered'}
    assert response.answer_type != 'insufficient_context'
    assert response.sources
    if response.answer_type == 'partial_answer':
        assert response.answer.startswith(PARTIAL_PREFIX)


def test_insufficient_answer_text_forces_insufficient_context(monkeypatch, tmp_path: Path):
    chunk = _chunk(0, 'Noi dung co lien quan so bo nhung khong du de ket luan.')
    retrieved = [
        RetrievedChunk(
            chunk=chunk,
            vector_score=0.7,
            keyword_score=0.0,
            final_score=0.7,
            selected_for_context=True,
            reason='test',
        )
    ]

    monkeypatch.setattr(RagPipeline, '_retrieve', lambda self, request: retrieved)
    monkeypatch.setattr(pipeline_module.LlmService, 'answer', lambda self, question, chunks: 'Khong du thong tin de tra loi cau hoi nay.')

    response = RagPipeline(_settings(tmp_path)).ask(_request('Cau hoi bat ky?'))

    assert response.answer_type == 'insufficient_context'
    assert response.confidence <= 0.25
    assert response.sources == []


def test_sources_empty_with_related_chunks_is_not_answered(monkeypatch, tmp_path: Path):
    chunk = _chunk(0, 'Related but weak content.')
    retrieved = [
        RetrievedChunk(
            chunk=chunk,
            vector_score=0.4,
            keyword_score=0.0,
            final_score=0.4,
            selected_for_context=False,
            reason='below threshold',
        )
    ]

    monkeypatch.setattr(RagPipeline, '_retrieve', lambda self, request: retrieved)

    response = RagPipeline(_settings(tmp_path)).ask(_request('Unrelated question?'))

    assert response.answer_type != 'answered'
    assert response.sources == []
    assert response.related_chunks


def test_insufficient_answer_with_source_text_exposes_selected_sources(monkeypatch, tmp_path: Path):
    chunk = _chunk(0, 'Việt Nam mở rộng quan hệ đối ngoại trong giai đoạn 1986-2000.')
    retrieved = [
        RetrievedChunk(
            chunk=chunk,
            vector_score=0.8,
            keyword_score=0.0,
            final_score=0.8,
            selected_for_context=True,
            reason='test',
        )
    ]

    monkeypatch.setattr(RagPipeline, '_retrieve', lambda self, request: retrieved)
    monkeypatch.setattr(
        pipeline_module.LlmService,
        'answer',
        lambda self, question, chunks: (
            'Không có thông tin đầy đủ để trả lời chính xác. '
            'Nguồn: [Nguồn 1] fileName=history.pdf, pageNumber=1, chunkIndex=0.'
        ),
    )

    response = RagPipeline(_settings(tmp_path)).ask(_request('Việt Nam bình thường hóa quan hệ với Hoa Kỳ vào năm nào?'))

    assert response.answer_type == 'insufficient_context'
    assert response.sources
    assert response.sources[0].file_name == 'econometrics.pdf'
    assert response.sources[0].page_start == 1


def test_build_controlled_refusal_for_dinh_topic():
    answer = build_controlled_refusal('Đinh Bộ Lĩnh là ai?')

    assert 'Tài liệu hiện tại không chứa thông tin về Đinh Bộ Lĩnh' in answer
    assert 'giai đoạn 1986–2000' in answer
    assert 'thế kỷ X hoặc thời Đinh' in answer


def test_out_of_scope_question_uses_controlled_refusal(monkeypatch, tmp_path: Path):
    chunk = _chunk(0, 'Nội dung giai đoạn 1986-2000, không phải thời Đinh.')
    retrieved = [
        RetrievedChunk(
            chunk=chunk,
            vector_score=0.8,
            keyword_score=0.0,
            final_score=0.8,
            selected_for_context=True,
            reason='test',
        )
    ]

    monkeypatch.setattr(RagPipeline, '_retrieve', lambda self, request: retrieved)

    response = RagPipeline(_settings(tmp_path)).ask(_request('Đinh Bộ Lĩnh là ai?'))

    assert response.answer_type == 'out_of_scope'
    assert 'Tài liệu hiện tại không chứa thông tin về Đinh Bộ Lĩnh' in response.answer
    assert response.sources == []
