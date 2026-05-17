from pathlib import Path

from app.models.schemas import Chunk


class PromptBuilder:
    def __init__(self):
        self.template_path = Path(__file__).resolve().parents[2].joinpath('prompts/rag_prompt.txt')

    def build(self, question: str, chunks: list[Chunk]) -> str:
        template = self.template_path.read_text(encoding='utf-8')
        context = '\n\n'.join(
            f'[{index + 1}] file={chunk.file_name}, page={chunk.page_start}-{chunk.page_end}, chunk_id={chunk.chunk_id}\n{chunk.content}'
            for index, chunk in enumerate(chunks)
        )
        return template.format(context=context, question=question)
