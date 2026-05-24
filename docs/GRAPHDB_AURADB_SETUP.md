# Neo4j AuraDB Mini GraphRAG Phase 1

Phase 1 stores extracted entity relations for offline inspection and retrieval. It does not add graph context to `/rag/ask`.

## Configuration

Keep live values in `rag-api/.env` only. Use `rag-api/.env.example` as a placeholder template:

```env
NEO4J_URI=neo4j+ssc://your-instance.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=
NEO4J_DATABASE=neo4j
```

The scripts do not print `NEO4J_PASSWORD` or the full URI.

## Graph Schema

Nodes:

- `(:Document {documentId, fileName, title, createdAt})`
- `(:Chunk {chunkId, documentId, pageNumber, chunkIndex, textPreview})`
- `(:Entity {entityKey, name, normalizedName, type, description})`

Relationships:

- `(:Document)-[:HAS_CHUNK]->(:Chunk)`
- `(:Chunk)-[:MENTIONS]->(:Entity)`
- `(:Entity)-[:RELATE_TO {relationType, description, confidence, documentId, fileName, pageNumber, chunkIndex, chunkId}]->(:Entity)`

Every extracted relation is traceable to its source chunk.

## Commands

Run from `rag-api`:

```powershell
python scripts/test_neo4j_connection.py
python scripts/init_graph_schema.py
python scripts/build_graph_from_chunks.py --limit 5 --dry-run
python scripts/build_graph_from_chunks.py --limit 20 --resume
python scripts/smoke_test_graph_rag.py
```

Pass `--document-id <id>` to scope ingestion or retrieval explicitly. Without it, the build script selects the stored document with the largest number of discoverable chunks.

Successful ingestion writes checkpoints to `storage/graph/graph_ingest_<documentId>.jsonl`. This runtime directory is ignored by Git.

Do not ingest more than the reviewed sample until extraction quality is acceptable.
