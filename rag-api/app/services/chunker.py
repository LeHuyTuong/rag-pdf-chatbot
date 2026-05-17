import re
import uuid

from app.config import Settings
from app.core.logging import get_logger
from app.models.schemas import Chunk, PageText

logger = get_logger(__name__)


class Chunker:
    def __init__(self, settings: Settings):
        self.settings = settings

    def chunk(self, pages: list[PageText], document_id: str, user_id: str, file_name: str) -> list[Chunk]:
        chunks: list[Chunk] = []
        chunk_size = max(1, self.settings.chunk_size)
        overlap = min(max(0, self.settings.chunk_overlap), max(0, chunk_size - 1))

        for page in pages:
            text = self._normalize(page.text)
            if not text:
                continue

            words = text.split()
            if not words:
                continue

            start = 0
            while start < len(words):
                end = min(start + chunk_size, len(words))
                content = ' '.join(words[start:end]).strip()
                if content:
                    chunks.append(self._make_chunk(chunks, document_id, user_id, file_name, page, text, content, start, end))
                if end >= len(words):
                    break
                start = max(end - overlap, start + 1)

        logger.info(
            'chunker complete document_id=%s pages=%s chunks=%s chunk_size=%s overlap=%s',
            document_id,
            len(pages),
            len(chunks),
            chunk_size,
            overlap,
        )
        return chunks

    def _make_chunk(
        self,
        chunks: list[Chunk],
        document_id: str,
        user_id: str,
        file_name: str,
        page: PageText,
        normalized_page_text: str,
        content: str,
        word_start: int,
        word_end: int,
    ) -> Chunk:
        token_count = len(content.split())
        reason = (
            f'Created from page {page.page_number}, words {word_start + 1}-{word_end}, '
            f'with CHUNK_SIZE={self.settings.chunk_size} and overlap={self.settings.chunk_overlap}.'
        )
        start = normalized_page_text.find(content[: min(80, len(content))])
        char_start = page.char_start + max(start, 0)
        return Chunk(
            chunk_id=str(uuid.uuid4()),
            document_id=document_id,
            user_id=user_id,
            chunk_index=len(chunks),
            page_start=page.page_number,
            page_end=page.page_number,
            char_start=char_start,
            char_end=char_start + len(content),
            token_count=token_count,
            content=content,
            chunk_reason=reason,
            file_name=file_name,
        )

    def _normalize(self, text: str) -> str:
        text = text.replace('\x00', ' ')
        text = re.sub(r'[ \t\r\f\v]+', ' ', text)
        text = re.sub(r'\n\s*\n+', '\n', text)
        return text.strip()
