from app.infrastructure.qdrant.qdrant_service import QdrantService


class QdrantCollectionManager:
    def __init__(self, qdrant: QdrantService):
        self.qdrant = qdrant

    def ensure(self) -> None:
        self.qdrant.ensure_collection()
