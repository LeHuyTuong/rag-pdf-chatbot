import hashlib
import math
import numpy as np
from app.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class EmbeddingService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._model = None

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self.settings.fast_test_mode:
            vectors = [self._hash_embedding(t) for t in texts]
        else:
            try:
                from sentence_transformers import SentenceTransformer
                if self._model is None:
                    self._model = SentenceTransformer(self.settings.embedding_model)
                vectors = self._model.encode(texts, normalize_embeddings=True).tolist()
            except Exception:
                vectors = [self._hash_embedding(t) for t in texts]
        for vector in vectors:
            if len(vector) != self.settings.embedding_dimension:
                raise ValueError(f'Embedding dimension mismatch: got {len(vector)}, expected {self.settings.embedding_dimension}')
        logger.info('embedded chunks count=%s', len(vectors))
        return vectors

    def _hash_embedding(self, text: str) -> list[float]:
        vector = np.zeros(self.settings.embedding_dimension, dtype=np.float32)
        for token in text.lower().split():
            digest = hashlib.sha256(token.encode()).digest()
            idx = int.from_bytes(digest[:4], 'big') % self.settings.embedding_dimension
            vector[idx] += 1 if digest[4] % 2 == 0 else -1
        norm = math.sqrt(float(np.dot(vector, vector))) or 1.0
        return (vector / norm).tolist()
