import argparse
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any

import pymysql
import requests
from dotenv import load_dotenv


if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')


ROOT_DIR = Path(__file__).resolve().parents[2]
RAG_API_DIR = Path(__file__).resolve().parents[1]

QUESTIONS = [
    '\u004e\u1ed9i dung ch\u00ednh c\u1ee7a t\u00e0i li\u1ec7u n\u00e0y l\u00e0 g\u00ec?',
    '\u0110\u1ea1i h\u1ed9i VI c\u00f3 \u00fd ngh\u0129a g\u00ec?',
    'V\u00ec sao Vi\u1ec7t Nam ph\u1ea3i ti\u1ebfn h\u00e0nh c\u00f4ng cu\u1ed9c \u0110\u1ed5i m\u1edbi t\u1eeb n\u0103m 1986?',
    '\u004e\u1ed9i dung tr\u1ecdng t\u00e2m c\u1ee7a \u0111\u01b0\u1eddng l\u1ed1i \u0110\u1ed5i m\u1edbi \u0111\u01b0\u1ee3c \u0111\u1ec1 ra t\u1ea1i \u0110\u1ea1i h\u1ed9i VI l\u00e0 g\u00ec?',
    'So s\u00e1nh t\u00ecnh h\u00ecnh Vi\u1ec7t Nam tr\u01b0\u1edbc v\u00e0 sau \u0110\u1ed5i m\u1edbi?',
]

OLD_NON_DIACRITIC_PHRASES = [
    'Dua tren',
    'Khong co thong tin',
    'Khong tim thay',
    'Tai lieu nay',
    'cac doan tai lieu',
    'No reliable source found',
]

ANALYTICAL_KEYWORDS = [
    '\u0110\u1ed5i m\u1edbi',
    '\u0110\u1ea1i h\u1ed9i VI',
    'sai l\u1ea7m',
    'khuy\u1ebft \u0111i\u1ec3m',
    'kh\u1ee7ng ho\u1ea3ng',
    'c\u01a1 ch\u1ebf',
    'quan li\u00eau',
    'bao c\u1ea5p',
    'c\u00f4ng nghi\u1ec7p h\u00f3a',
]

DIACRITIC_CHARS = set(
    '\u0103\u00e2\u0111\u00ea\u00f4\u01a1\u01b0'
    '\u00e1\u00e0\u1ea3\u00e3\u1ea1\u1ea5\u1ea7\u1ea9\u1eab\u1ead\u1eaf\u1eb1\u1eb3\u1eb5\u1eb7'
    '\u00e9\u00e8\u1ebb\u1ebd\u1eb9\u1ebf\u1ec1\u1ec3\u1ec5\u1ec7'
    '\u00ed\u00ec\u1ec9\u0129\u1ecb'
    '\u00f3\u00f2\u1ecf\u00f5\u1ecd\u1ed1\u1ed3\u1ed5\u1ed7\u1ed9\u1edb\u1edd\u1edf\u1ee1\u1ee3'
    '\u00fa\u00f9\u1ee7\u0169\u1ee5\u1ee9\u1eeb\u1eed\u1eef\u1ef1'
    '\u00fd\u1ef3\u1ef7\u1ef9\u1ef5'
)


def load_env() -> None:
    load_dotenv(ROOT_DIR / '.env')
    load_dotenv(RAG_API_DIR / '.env', override=True)


def has_vietnamese_diacritics(text: str) -> bool:
    return any(ch in DIACRITIC_CHARS for ch in (text or '').lower())


def compact(text: str, limit: int = 320) -> str:
    return re.sub(r'\s+', ' ', text or '').strip()[:limit]


def db_config() -> dict[str, Any]:
    return {
        'host': os.getenv('DB_HOST', '127.0.0.1'),
        'port': int(os.getenv('DB_PORT', '3306')),
        'user': os.getenv('DB_USERNAME', 'raguser'),
        'password': os.getenv('DB_PASSWORD', 'ragpass'),
        'database': os.getenv('DB_DATABASE', 'rag'),
        'charset': 'utf8mb4',
        'cursorclass': pymysql.cursors.DictCursor,
    }


def to_api_uuid(value: Any) -> str:
    if isinstance(value, (bytes, bytearray)) and len(value) == 16:
        return str(uuid.UUID(bytes=bytes(value)))
    return str(value)


def discover_latest_document() -> tuple[str, str]:
    query = """
        SELECT id, user_id, file_name, total_chunks, status, updated_at
        FROM documents
        WHERE total_chunks IS NULL OR total_chunks > 0
        ORDER BY updated_at DESC, created_at DESC
        LIMIT 1
    """
    try:
        with pymysql.connect(**db_config()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)
                row = cursor.fetchone()
    except Exception as exc:
        raise RuntimeError(
            'Could not discover a smoke-test document from MySQL. '
            'Set SMOKE_USER_ID and SMOKE_DOCUMENT_ID, or start/configure MySQL.'
        ) from exc

    if not row:
        raise RuntimeError(
            'No ingested document found in MySQL. Upload/ingest a PDF first, '
            'or pass SMOKE_USER_ID and SMOKE_DOCUMENT_ID.'
        )

    print(
        '[setup] using latest document: '
        f'fileName={row.get("file_name")} status={row.get("status")} chunks={row.get("total_chunks")}'
    )
    return to_api_uuid(row['user_id']), to_api_uuid(row['id'])


def resolve_ids(args: argparse.Namespace) -> tuple[str, str]:
    user_id = args.user_id or os.getenv('SMOKE_USER_ID')
    document_id = args.document_id or os.getenv('SMOKE_DOCUMENT_ID')
    if user_id and document_id:
        return user_id, document_id
    return discover_latest_document()


def post_question(base_url: str, user_id: str, document_id: str, question: str) -> dict[str, Any]:
    payload = {
        'user_id': user_id,
        'document_id': document_id,
        'session_id': 'smoke-test-rag',
        'message_id': f'smoke-{uuid.uuid4().hex}',
        'question': question,
    }
    response = requests.post(f'{base_url.rstrip("/")}/rag/ask', json=payload, timeout=180)
    response.raise_for_status()
    return response.json()


def source_value(source: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = source.get(key)
        if value is not None:
            return value
    return None


def format_source(source: dict[str, Any]) -> str:
    file_name = source_value(source, 'fileName', 'file_name')
    page_number = source_value(source, 'pageNumber', 'page_start', 'page')
    chunk_index = source_value(source, 'chunkIndex', 'chunk_index')
    return f'fileName={file_name}, pageNumber={page_number}, chunkIndex={chunk_index}'


def source_has_citation(source: dict[str, Any]) -> bool:
    return (
        source_value(source, 'fileName', 'file_name') is not None
        and source_value(source, 'pageNumber', 'page_start', 'page') is not None
        and source_value(source, 'chunkIndex', 'chunk_index') is not None
    )


def evaluate_answer(question: str, data: dict[str, Any]) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    warnings: list[str] = []
    answer = data.get('answer') or ''
    answer_lower = answer.lower()

    if not answer.strip():
        failures.append('Empty answer')
    elif not has_vietnamese_diacritics(answer):
        failures.append('Answer has no Vietnamese diacritics')

    for phrase in OLD_NON_DIACRITIC_PHRASES:
        if phrase.lower() in answer_lower:
            failures.append(f'Answer contains old non-diacritic phrase: "{phrase}"')

    sources = data.get('sources') or []
    if not sources:
        failures.append('Empty sources')
    elif any(not source_has_citation(source) for source in sources):
        failures.append('One or more sources are missing fileName/pageNumber/chunkIndex')

    if 'v\u00ec sao' in question.lower():
        if not any(keyword.lower() in answer_lower for keyword in ANALYTICAL_KEYWORDS):
            warnings.append('Analytical answer does not mention any expected Doi moi keyword')

    return failures, warnings


def run() -> int:
    load_env()
    parser = argparse.ArgumentParser(description='Smoke-test local RAG API answer quality.')
    parser.add_argument('--api-url', default=os.getenv('RAG_API_URL', 'http://localhost:8001'))
    parser.add_argument('--user-id')
    parser.add_argument('--document-id')
    args = parser.parse_args()

    try:
        user_id, document_id = resolve_ids(args)
    except RuntimeError as exc:
        print(f'[setup][FAIL] {exc}', file=sys.stderr)
        return 2

    passed = 0
    failed = 0

    for index, question in enumerate(QUESTIONS, start=1):
        print(f'\n[{index}] {question}')
        try:
            data = post_question(args.api_url, user_id, document_id, question)
            failures, warnings = evaluate_answer(question, data)
        except requests.RequestException as exc:
            data = {}
            failures = [f'RAG API request failed: {exc}']
            warnings = []

        print(f'Answer preview: {compact(data.get("answer", ""))}')
        sources = data.get('sources') or []
        print(f'Sources: {len(sources)}')
        for source in sources[:5]:
            print(f'- {format_source(source)}')
        for warning in warnings:
            print(f'Warning: {warning}')

        if failures:
            failed += 1
            print('Status: FAIL')
            print('Reason:')
            for failure in failures:
                print(f'- {failure}')
        else:
            passed += 1
            print('Status: PASS')

    print('\nSummary')
    print(f'Total: {len(QUESTIONS)}')
    print(f'Passed: {passed}')
    print(f'Failed: {failed}')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(run())
