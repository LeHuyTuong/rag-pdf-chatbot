from qdrant_client import QdrantClient
from qdrant_client.http import models as qm
from pathlib import Path
from app.config import Settings
from app.core.logging import get_logger
from app.models.schemas import Chunk
from app.services.embedding_service import EmbeddingService

logger = get_logger(__name__)


class QdrantService:
    def __init__(self, settings: Settings, embedding: EmbeddingService):
        self.settings = settings
        self.embedding = embedding
        self.collection = settings.qdrant_collection
        self.client = None
        self._using_local = False
        self._disabled_reason = None
        try:
            self.client = QdrantClient(settings.qdrant_url, api_key=settings.qdrant_api_key or None)
        except Exception as e:
            self.client = None
            self._disabled_reason = str(e)
            logger.warning('Qdrant disabled: %s', self._disabled_reason)

    def ensure_collection(self) -> None:
        if self.client is None:
            self._enable_local_fallback('initial Qdrant client was not created')
        try:
            names = [c.name for c in self.client.get_collections().collections]
        except Exception as error:
            if not self._using_local:
                self._enable_local_fallback(str(error))
                try:
                    names = [c.name for c in self.client.get_collections().collections]
                except Exception as local_error:
                    self.client = None
                    self._disabled_reason = str(local_error)
                    logger.warning('Qdrant disabled after local fallback failed: %s', self._disabled_reason)
                    return
            else:
                self.client = None
                self._disabled_reason = str(error)
                logger.warning('Qdrant disabled: %s', self._disabled_reason)
                return
        if self.collection not in names:
            self.client.create_collection(self.collection, vectors_config=qm.VectorParams(size=self.settings.embedding_dimension, distance=qm.Distance.COSINE))
        for field in ['user_id', 'document_id', 'source_type', 'file_name']:
            try:
                self.client.create_payload_index(self.collection, field_name=field, field_schema=qm.PayloadSchemaType.KEYWORD)
            except Exception:
                pass

    def _enable_local_fallback(self, reason: str) -> None:
        base = Path(self.settings.qdrant_local_path) if self.settings.qdrant_local_path else Path(self.settings.debug_report_path).parent / 'qdrant-local'
        base.mkdir(parents=True, exist_ok=True)
        self.client = QdrantClient(path=str(base))
        self._using_local = True
        self._disabled_reason = None
        logger.warning('Qdrant HTTP unavailable (%s); using local Qdrant path: %s', reason, base)

    def upsert_chunks(self, chunks: list[Chunk]) -> list[Chunk]:
        # If client is disabled, skip embedding/upsert but still return chunks
        if self.client is None:
            logger.warning('QdrantService.upsert_chunks skipped because client is disabled')
            return chunks

        self.ensure_collection()
        if self.client is None:
            logger.warning('QdrantService.upsert_chunks skipped after connection failure')
            return chunks
        vectors = self.embedding.embed([c.content for c in chunks])
        points = []
        for chunk, vector in zip(chunks, vectors):
            chunk.qdrant_point_id = chunk.chunk_id
            points.append(qm.PointStruct(
                id=chunk.chunk_id,
                vector=vector,
                payload={
                    'user_id': chunk.user_id,
                    'document_id': chunk.document_id,
                    'chunk_id': chunk.chunk_id,
                    'file_name': chunk.file_name,
                    'page_start': chunk.page_start,
                    'page_end': chunk.page_end,
                    'source_type': 'uploaded_pdf',
                    'token_count': chunk.token_count,
                    'content': chunk.content,
                    'chunk_index': chunk.chunk_index,
                    'chunk_reason': chunk.chunk_reason,
                    'char_start': chunk.char_start,
                    'char_end': chunk.char_end,
                },
            ))
        try:
            self.client.upsert(self.collection, points=points)
        except Exception as e:
            logger.warning('Qdrant upsert failed: %s', e)
        return chunks

    def search(self, user_id: str, document_id: str, question: str, top_k: int) -> list[tuple[Chunk, float]]:
        if self.client is None:
            logger.warning('QdrantService.search skipped because client is disabled')
            return []

        self.ensure_collection()
        if self.client is None:
            logger.warning('QdrantService.search skipped after connection failure')
            return []
        filters = qm.Filter(must=[
            qm.FieldCondition(key='user_id', match=qm.MatchValue(value=user_id)),
            qm.FieldCondition(key='document_id', match=qm.MatchValue(value=document_id)),
        ])
        hits = self.client.search(self.collection, query_vector=self.embedding.embed([question])[0], query_filter=filters, limit=top_k, with_payload=True)
        result = []
        for hit in hits:
            p = hit.payload or {}
            chunk = Chunk(
                chunk_id=p['chunk_id'], document_id=p['document_id'], user_id=p['user_id'], chunk_index=p.get('chunk_index', 0),
                page_start=p['page_start'], page_end=p['page_end'], char_start=p.get('char_start', 0), char_end=p.get('char_end', 0),
                token_count=p['token_count'], content=p.get('content', ''), chunk_reason=p.get('chunk_reason', ''), file_name=p['file_name'], qdrant_point_id=str(hit.id)
            )
            result.append((chunk, float(hit.score)))
        return result
