import argparse
import json
import os
import re
import sys
import uuid
from pathlib import Path

import requests


if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')


DEFAULT_QUESTIONS = [
    'N\u1ed9i dung ch\u00ednh c\u1ee7a t\u00e0i li\u1ec7u n\u00e0y l\u00e0 g\u00ec?',
    'V\u00ec sao Vi\u1ec7t Nam ph\u1ea3i ti\u1ebfn h\u00e0nh c\u00f4ng cu\u1ed9c \u0110\u1ed5i m\u1edbi t\u1eeb n\u0103m 1986?',
]

RELEVANT_MARKERS = (
    '\u0111\u1ea1i h\u1ed9i',
    'sai l\u1ea7m',
    'khuy\u1ebft \u0111i\u1ec3m',
    'kh\u1ee7ng ho\u1ea3ng',
    'c\u01a1 ch\u1ebf',
    'quan li\u00eau',
    'bao c\u1ea5p',
    '1976-1980',
    '1976',
)

LOW_VALUE_MARKERS = (
    't\u00e0i li\u1ec7u tham kh\u1ea3o',
    'ph\u1ee5 l\u1ee5c \u1ea3nh',
    '\u1ea3nh ch\u1ee5p',
    'ngu\u1ed3n: http',
    'http://',
    'https://',
)

DIACRITIC_CHARS = set(
    '\u0103\u00e2\u0111\u00ea\u00f4\u01a1\u01b0'
    '\u00e1\u00e0\u1ea3\u00e3\u1ea1\u1ea5\u1ea7\u1ea9\u1eab\u1ead\u1eaf\u1eb1\u1eb3\u1eb5\u1eb7'
    '\u00e9\u00e8\u1ebb\u1ebd\u1eb9\u1ebf\u1ec1\u1ec3\u1ec5\u1ec7'
    '\u00ed\u00ec\u1ec9\u0129\u1ecb'
    '\u00f3\u00f2\u1ecf\u00f5\u1ecd\u1ed1\u1ed3\u1ed5\u1ed7\u1ed9\u1edb\u1edd\u1edf\u1ee1\u1ee3'
    '\u00fa\u00f9\u1ee7\u0169\u1ee5\u1ee9\u1eeb\u1eed\u1eef\u1ef1'
    '\u00fd\u1ef3\u1ef7\u1ef9\u1ef5'
)


def has_vietnamese_diacritics(text: str) -> bool:
    return any(ch in DIACRITIC_CHARS for ch in (text or '').lower())


def post_question(base_url: str, user_id: str, document_id: str, question: str) -> dict:
    message_id = f'smoke-{uuid.uuid4().hex}'
    payload = {
        'user_id': user_id,
        'document_id': document_id,
        'session_id': 'smoke-rag-quality',
        'message_id': message_id,
        'question': question,
    }
    response = requests.post(f'{base_url.rstrip("/")}/rag/ask', json=payload, timeout=180)
    response.raise_for_status()
    data = response.json()
    data['_message_id'] = message_id
    return data


def load_report(report_path: str | None) -> dict:
    if not report_path:
        return {}
    path = Path(report_path)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding='utf-8'))


def source_has_required_fields(source: dict) -> bool:
    has_file = bool(source.get('file_name') or source.get('fileName'))
    has_page = source.get('page_start') is not None or source.get('pageNumber') is not None
    has_chunk = source.get('chunk_index') is not None or source.get('chunkIndex') is not None
    return has_file and has_page and has_chunk


def check_answer(question: str, data: dict, report: dict) -> list[str]:
    failures: list[str] = []
    answer = data.get('answer') or ''

    if not has_vietnamese_diacritics(answer):
        failures.append('answer does not contain Vietnamese diacritics')

    if data.get('answer_type') not in {'answered', 'partial_answer'}:
        failures.append(f'answer_type is {data.get("answer_type")!r}')

    sources = data.get('sources') or []
    if not sources:
        failures.append('no answer sources returned')
    elif not all(source_has_required_fields(source) for source in sources):
        failures.append('one or more sources are missing fileName/pageNumber/chunkIndex data')

    lowered_question = question.lower()
    if 'v\u00ec sao' in lowered_question or '\u0111\u1ed5i m\u1edbi' in lowered_question:
        retrieved = report.get('retrieved_chunks') or []
        top = retrieved[: max(1, min(5, len(retrieved)))]
        preview_blob = ' '.join((item.get('preview') or '').lower() for item in top)
        if not any(marker in preview_blob for marker in RELEVANT_MARKERS):
            failures.append('top retrieval previews do not include analytical Doi moi markers')
        low_value_top = [
            item for item in top
            if any(marker in (item.get('preview') or '').lower() for marker in LOW_VALUE_MARKERS)
        ]
        if len(low_value_top) >= max(2, len(top) // 2):
            failures.append('top retrieval previews are dominated by captions/references/URLs')

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description='Smoke-test RAG answer quality over the running FastAPI service.')
    parser.add_argument('--base-url', default=os.getenv('RAG_BASE_URL', 'http://127.0.0.1:8001'))
    parser.add_argument('--user-id', default=os.getenv('SMOKE_USER_ID'))
    parser.add_argument('--document-id', default=os.getenv('SMOKE_DOCUMENT_ID'))
    parser.add_argument('--question', action='append', dest='questions')
    args = parser.parse_args()

    if not args.user_id or not args.document_id:
        print('SMOKE_USER_ID and SMOKE_DOCUMENT_ID are required, or pass --user-id and --document-id.', file=sys.stderr)
        return 2

    questions = args.questions or DEFAULT_QUESTIONS
    failed = False
    for question in questions:
        print(f'\n[smoke] question: {question}')
        data = post_question(args.base_url, args.user_id, args.document_id, question)
        report = load_report(data.get('retrieval_report_path'))
        failures = check_answer(question, data, report)
        print(f'[smoke] answer_type={data.get("answer_type")} confidence={data.get("confidence")}')
        print(f'[smoke] sources={len(data.get("sources") or [])} report={data.get("retrieval_report_path")}')
        print('[smoke] answer preview:', re.sub(r'\s+', ' ', (data.get('answer') or '')[:300]).strip())
        if failures:
            failed = True
            for item in failures:
                print(f'[smoke][FAIL] {item}')
        else:
            print('[smoke][PASS]')

    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
