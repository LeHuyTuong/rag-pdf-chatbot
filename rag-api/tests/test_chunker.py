from app.config import Settings
from app.models.schemas import PageText
from app.services.chunker import Chunker


def test_chunker_creates_reasoned_page_aware_chunks():
    settings = Settings(CHUNK_SIZE=40, CHUNK_OVERLAP=5)
    pages = [PageText(page_number=1, text=("Chiến thắng Bạch Đằng năm 938 do Ngô Quyền lãnh đạo. " * 20))]
    chunks = Chunker(settings).chunk(pages, "doc1", "user1", "sample.pdf")
    assert len(chunks) >= 2
    assert all(c.page_start == 1 and c.page_end == 1 for c in chunks)
    assert all("CHUNK_SIZE=40" in c.chunk_reason for c in chunks)
    assert all(c.token_count <= 45 for c in chunks)
