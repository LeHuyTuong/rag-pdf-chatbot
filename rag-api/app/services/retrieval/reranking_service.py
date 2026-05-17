from app.models.schemas import RetrievedChunk


class RerankingService:
    def rerank(self, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        return chunks
