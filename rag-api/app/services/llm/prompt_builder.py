from pathlib import Path

from app.models.schemas import Chunk


class PromptBuilder:
    def __init__(self):
        self.template_path = Path(__file__).resolve().parents[2].joinpath('prompts/rag_prompt.txt')

    def build(self, question: str, chunks: list[Chunk]) -> str:
        """
        Xây dựng prompt cho LLM từ `question` và danh sách `chunks`.

        Format trả về phù hợp với template `prompts/rag_prompt.txt`.
        """
        template = self.template_path.read_text(encoding='utf-8')
        context = '\n\n'.join(
            f'[Nguồn {index + 1}] fileName={chunk.file_name}, pageNumber={chunk.page_start}-{chunk.page_end}, '
            f'chunkIndex={chunk.chunk_index}, chunkId={chunk.chunk_id}\n{chunk.content}'
            for index, chunk in enumerate(chunks)
        )
        return template.format(context=context, question=question)
