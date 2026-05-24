import json
import uuid
from collections import Counter
from pathlib import Path

from qdrant_client import QdrantClient

from app.config import Settings, get_settings
from app.graph.graph_extractor import GraphExtractor
from app.graph.graph_schema import GraphChunk, GraphExtractionResult
from app.graph.neo4j_client import Neo4jClient
from app.services.mysql_service import MySqlService


class ExistingChunkLoader:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.source_name = 'none'

    def load_chunks(
        self,
        document_id: str | None = None,
        limit: int | None = None,
        start_from_chunk_index: int | None = None,
        exclude_chunk_ids: set[str] | None = None,
    ) -> tuple[str | None, list[GraphChunk]]:
        excluded = exclude_chunk_ids or set()
        qdrant_chunks = self._qdrant_chunks()
        if qdrant_chunks:
            selected_document_id = document_id or self._select_document(qdrant_chunks)
            selected = self._filter(
                qdrant_chunks, selected_document_id, limit, start_from_chunk_index, excluded
            )
            if selected or document_id is None:
                self.source_name = 'qdrant'
                return selected_document_id, selected
        mysql_chunks = self._mysql_chunks()
        self.source_name = 'mysql' if mysql_chunks else 'none'
        selected_document_id = document_id or self._select_document(mysql_chunks)
        return selected_document_id, self._filter(
            mysql_chunks, selected_document_id, limit, start_from_chunk_index, excluded
        )

    def _qdrant_chunks(self) -> list[GraphChunk]:
        try:
            client = QdrantClient(self.settings.qdrant_url, api_key=self.settings.qdrant_api_key or None)
            rows = []
            offset = None
            while True:
                points, offset = client.scroll(
                    collection_name=self.settings.qdrant_collection,
                    limit=256,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )
                rows.extend(point.payload or {} for point in points)
                if offset is None:
                    return [chunk for row in rows if (chunk := self._from_row(row)) is not None]
        except Exception:
            return []

    def _mysql_chunks(self) -> list[GraphChunk]:
        try:
            with MySqlService(self.settings).connect() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        '''
                        select id as chunk_id, document_id, file_name, page_start, chunk_index, content
                        from document_chunks order by document_id, chunk_index
                        '''
                    )
                    return [chunk for row in cursor.fetchall() if (chunk := self._from_row(row)) is not None]
        except Exception:
            return []

    @staticmethod
    def _from_row(row: dict) -> GraphChunk | None:
        document_id = ExistingChunkLoader._identifier(row.get('document_id'))
        if not document_id:
            return None
        page_number = row.get('page_number', row.get('page_start'))
        chunk_index = row.get('chunk_index')
        chunk_id = ExistingChunkLoader._identifier(row.get('chunk_id')) or f'{document_id}_{page_number}_{chunk_index}'
        text = str(row.get('text') or row.get('content') or '')
        if not text:
            return None
        return GraphChunk(
            chunk_id=chunk_id,
            document_id=document_id,
            file_name=str(row.get('file_name') or 'uploaded_document'),
            page_number=int(page_number) if page_number is not None else None,
            chunk_index=int(chunk_index) if chunk_index is not None else None,
            text=text,
        )

    @staticmethod
    def _identifier(value: object) -> str:
        if isinstance(value, memoryview):
            value = value.tobytes()
        if isinstance(value, bytes) and len(value) == 16:
            return str(uuid.UUID(bytes=value))
        if isinstance(value, bytes):
            return value.decode('utf-8', errors='replace')
        return str(value or '')

    @staticmethod
    def _select_document(chunks: list[GraphChunk]) -> str | None:
        if not chunks:
            return None
        counts = Counter(chunk.document_id for chunk in chunks)
        return sorted(counts, key=lambda item: (-counts[item], item))[0]

    @staticmethod
    def _filter(
        chunks: list[GraphChunk],
        document_id: str | None,
        limit: int | None,
        start_from_chunk_index: int | None,
        excluded: set[str],
    ) -> list[GraphChunk]:
        filtered = [
            chunk
            for chunk in chunks
            if (document_id is None or chunk.document_id == document_id)
            and chunk.chunk_id not in excluded
            and (start_from_chunk_index is None or (chunk.chunk_index or 0) >= start_from_chunk_index)
        ]
        filtered.sort(key=lambda chunk: (chunk.chunk_index if chunk.chunk_index is not None else -1, chunk.chunk_id))
        return filtered[:limit] if limit is not None else filtered


class GraphIngestionService:
    def __init__(
        self,
        client: Neo4jClient,
        extractor: GraphExtractor,
    ):
        self.client = client
        self.extractor = extractor

    def ingest_chunk(self, chunk: GraphChunk) -> tuple[GraphExtractionResult, int, int]:
        extraction = self.extractor.extract(chunk)
        self.upsert_extraction(chunk, extraction)
        return extraction, len(extraction.entities), len(extraction.relations)

    def upsert_extraction(self, chunk: GraphChunk, extraction: GraphExtractionResult) -> tuple[int, int]:
        self.client.upsert_document(chunk.document_id, chunk.file_name)
        self.client.upsert_chunk(
            chunk.chunk_id,
            chunk.document_id,
            chunk.file_name,
            chunk.page_number,
            chunk.chunk_index,
            chunk.text,
        )
        self.client.clear_chunk_evidence(chunk.chunk_id)
        for entity in extraction.entities:
            self.client.upsert_entity(entity, chunk.chunk_id)
        for relation in extraction.relations:
            self.client.upsert_relation(relation)
        return len(extraction.entities), len(extraction.relations)


def read_processed_chunk_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    processed = set()
    for line in path.read_text(encoding='utf-8').splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if payload.get('status') == 'ok' and payload.get('chunk_id'):
            processed.add(payload['chunk_id'])
    return processed
