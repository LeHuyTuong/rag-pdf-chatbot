import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.graph.graph_extractor import GraphExtractor
from app.graph.graph_ingestion import ExistingChunkLoader, GraphIngestionService, read_processed_chunk_ids
from app.graph.neo4j_client import Neo4jClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Build a bounded Neo4j graph sample from existing RAG chunks.')
    parser.add_argument('--document-id', default=None, help='Existing document ID. If omitted, select the largest stored document.')
    parser.add_argument('--limit', type=positive_integer, default=20, help='Maximum chunks to extract in this run. Default: 20.')
    parser.add_argument('--resume', action='store_true', help='Skip chunks already marked successful in the document checkpoint.')
    parser.add_argument('--dry-run', action='store_true', help='Extract and print summaries without writing Neo4j or a checkpoint.')
    parser.add_argument('--clear-document', action='store_true', help='Remove this document graph before sample ingestion.')
    parser.add_argument('--start-from-chunk-index', type=int, default=None, help='Start at this existing chunk index.')
    parser.add_argument('--sleep-seconds', type=float, default=1.0, help='Pause between LLM extraction calls. Default: 1.')
    return parser.parse_args()


def positive_integer(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError('limit must be greater than zero')
    return number


def checkpoint_path(document_id: str) -> Path:
    safe_document_id = re.sub(r'[^A-Za-z0-9_.-]+', '_', document_id)
    return Path(__file__).resolve().parents[1] / 'storage' / 'graph' / f'graph_ingest_{safe_document_id}.jsonl'


def append_checkpoint(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + '\n')


def source_warning(text: str) -> str | None:
    if '\u25a0' in text or '\ufffd' in text:
        return 'source text contains replacement glyphs; review input quality before ingestion'
    return None


def display_extraction(chunk, extraction, prefix: str) -> None:
    print(
        f'{prefix} page={chunk.page_number} chunk={chunk.chunk_index} '
        f'entities={len(extraction.entities)} relations={len(extraction.relations)}'
    )
    for entity in extraction.entities[:6]:
        print(f'  entity: {entity.name} [{entity.type}]')
    for relation in extraction.relations[:5]:
        print(
            f'  relation: {relation.source_entity.name} --{relation.relation_type}--> '
            f'{relation.target_entity.name} | {relation.description}'
        )


def main() -> int:
    args = parse_args()
    if args.clear_document and not args.document_id:
        print('--clear-document requires --document-id')
        return 2
    if args.clear_document and args.dry_run:
        print('--clear-document cannot be combined with --dry-run')
        return 2

    settings = get_settings()
    loader = ExistingChunkLoader(settings)
    selected_document_id, document_chunks = loader.load_chunks(
        document_id=args.document_id,
        start_from_chunk_index=args.start_from_chunk_index,
    )
    if not selected_document_id or not document_chunks:
        print('No existing stored chunks were found for graph extraction.')
        return 0
    if not args.document_id:
        print(f'auto_discovered_document_id={selected_document_id}')

    checkpoint = checkpoint_path(selected_document_id)
    if args.limit > 20 and not args.dry_run and not (args.resume and checkpoint.exists()):
        print('Refusing sample run above 20 chunks without --resume and an existing checkpoint.')
        return 2

    processed_ids = read_processed_chunk_ids(checkpoint) if args.resume else set()
    chunks = [chunk for chunk in document_chunks if chunk.chunk_id not in processed_ids][:args.limit]
    print(
        f'chunk_source={loader.source_name} document_id={selected_document_id} '
        f'available_chunks={len(document_chunks)} selected_chunks={len(chunks)} dry_run={args.dry_run}'
    )
    if not chunks:
        print('No unprocessed chunks matched this run.')
        return 0

    if args.clear_document:
        with Neo4jClient(settings) as client:
            client.verify_connectivity()
            client.clear_document(selected_document_id)
        if checkpoint.exists():
            checkpoint.unlink()
        print(f'cleared_document={selected_document_id}')

    extractor = GraphExtractor(settings)
    totals = {
        'chunks_processed': 0,
        'entities_extracted': 0,
        'relations_extracted': 0,
        'entities_upserted': 0,
        'relations_upserted': 0,
        'errors': 0,
    }

    client = None
    ingestion = None
    if not args.dry_run:
        client = Neo4jClient(settings)
        client.verify_connectivity()
        client.create_constraints()
        ingestion = GraphIngestionService(client, extractor)
    try:
        for position, chunk in enumerate(chunks, start=1):
            warning = source_warning(chunk.text)
            if warning:
                print(f'warning chunk_id={chunk.chunk_id}: {warning}')
                if not args.dry_run:
                    totals['errors'] += 1
                    print(f'[{position}/{len(document_chunks)}] page={chunk.page_number} chunk={chunk.chunk_index} status=skipped_source_quality')
                    append_checkpoint(
                        checkpoint,
                        {
                            'timestamp': datetime.now(timezone.utc).isoformat(),
                            'chunk_id': chunk.chunk_id,
                            'chunk_index': chunk.chunk_index,
                            'status': 'skipped_source_quality',
                            'error': warning,
                        },
                    )
                    continue
            extraction = extractor.extract(chunk)
            if extractor.last_error:
                totals['errors'] += 1
                print(f'[{position}/{len(document_chunks)}] page={chunk.page_number} chunk={chunk.chunk_index} status=error ({extractor.last_error})')
                if not args.dry_run:
                    append_checkpoint(
                        checkpoint,
                        {
                            'timestamp': datetime.now(timezone.utc).isoformat(),
                            'chunk_id': chunk.chunk_id,
                            'chunk_index': chunk.chunk_index,
                            'status': 'error',
                            'error': extractor.last_error,
                        },
                    )
                continue
            totals['chunks_processed'] += 1
            totals['entities_extracted'] += len(extraction.entities)
            totals['relations_extracted'] += len(extraction.relations)
            display_extraction(chunk, extraction, f'[{position}/{len(document_chunks)}]')
            if not args.dry_run and ingestion is not None:
                upserted_entities, upserted_relations = ingestion.upsert_extraction(chunk, extraction)
                totals['entities_upserted'] += upserted_entities
                totals['relations_upserted'] += upserted_relations
                append_checkpoint(
                    checkpoint,
                    {
                        'timestamp': datetime.now(timezone.utc).isoformat(),
                        'chunk_id': chunk.chunk_id,
                        'chunk_index': chunk.chunk_index,
                        'page_number': chunk.page_number,
                        'entities': upserted_entities,
                        'relations': upserted_relations,
                        'status': 'ok',
                    },
                )
                print(f'[{position}/{len(document_chunks)}] status=ok')
            if args.sleep_seconds > 0 and position < len(chunks):
                time.sleep(args.sleep_seconds)
    finally:
        if client is not None:
            client.close()

    print('Graph ingestion summary:')
    for name, value in totals.items():
        print(f'{name}: {value}')
    print(f'checkpoint: {"not_written_dry_run" if args.dry_run else checkpoint}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
