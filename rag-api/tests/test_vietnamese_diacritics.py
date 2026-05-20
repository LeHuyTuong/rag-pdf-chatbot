from app.config import Settings
from app.models.schemas import Chunk, PageText
from app.services.chunker import Chunker
from app.services.llm.prompt_builder import PromptBuilder


def test_chunker_preserves_vietnamese_diacritics():
    pages = [
        PageText(
            page_number=1,
            text='Đại hội VI mở đầu công cuộc Đổi mới, khắc phục khủng hoảng kinh tế - xã hội.',
        )
    ]

    chunks = Chunker(Settings(CHUNK_SIZE=100, CHUNK_OVERLAP=0)).chunk(pages, 'doc-1', 'user-1', 'lich-su.pdf')

    assert chunks
    assert 'Đại hội VI' in chunks[0].content
    assert 'Đổi mới' in chunks[0].content
    assert 'khủng hoảng' in chunks[0].content


def test_prompt_context_uses_original_vietnamese_text():
    chunk = Chunk(
        chunk_id='chunk-1',
        document_id='doc-1',
        user_id='user-1',
        chunk_index=3,
        page_start=38,
        page_end=38,
        char_start=0,
        char_end=100,
        token_count=20,
        content='Đại hội VI nhìn thẳng vào sự thật và đổi mới cơ chế quản lý kinh tế.',
        chunk_reason='test',
        file_name='lich-su.pdf',
    )

    prompt = PromptBuilder().build('Vì sao Việt Nam phải Đổi mới?', [chunk])

    assert 'Đại hội VI' in prompt
    assert 'đổi mới cơ chế quản lý kinh tế' in prompt
    assert 'chunkIndex=3' in prompt
