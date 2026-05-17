import argparse
import json
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pypdf import PdfReader, PdfWriter

from app.config import get_settings
from app.services.chunker import Chunker
from app.services.pdf_parser import PdfParser


TEXT_BODY = (
    "Phong thuy ung dung la tai lieu dung de kiem thu ingest PDF. "
    "Tai lieu co text layer, co ten file tieng Viet, va phai tao duoc chunk. "
    "Nguoi dung co the hoi ve noi dung phong thuy sau khi ingest thanh cong."
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--api-url', default=None, help='Optional RAG API URL, for example http://127.0.0.1:8001')
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix='rag_pdf_smoke_') as tmp:
        root = Path(tmp)
        cases = make_cases(root)
        results = [run_parser_case(name, path) for name, path in cases.items()]

        assert_case(results, 'normal_text.pdf', status='completed', chunks_gt=0)
        assert_case(results, 'SÁCH PHONG THỦY ỨNG DỤNG.pdf', status='completed', chunks_gt=0)
        assert_case(results, 'corrupt.pdf', status='failed', error_contains='PDF parser failed')
        assert_case(results, 'scan_like.pdf', status='failed', warning_contains='OCR is required')
        assert_case(results, 'encrypted.pdf', status='failed', error_contains='encrypted/password protected')

        payload = {'parser_chunker_cases': results}
        if args.api_url:
            api_results = [
                run_api_ingest(args.api_url.rstrip('/'), name, path)
                for name, path in cases.items()
            ]
            assert_case(api_results, 'normal_text.pdf', status='completed', chunks_gt=0)
            assert_case(api_results, 'SÁCH PHONG THỦY ỨNG DỤNG.pdf', status='completed', chunks_gt=0)
            assert_case(api_results, 'corrupt.pdf', status='failed', error_contains='PDF parser failed')
            assert_case(api_results, 'scan_like.pdf', status='failed', error_contains='OCR is required')
            assert_case(api_results, 'encrypted.pdf', status='failed', error_contains='encrypted/password protected')
            payload['api_ingest_cases'] = api_results

        safe_print(json.dumps(payload, ensure_ascii=False, indent=2))


def make_cases(root: Path) -> dict[str, Path]:
    normal = root / 'normal_text.pdf'
    unicode_pdf = root / 'SÁCH PHONG THỦY ỨNG DỤNG.pdf'
    corrupt = root / 'corrupt.pdf'
    scan_like = root / 'scan_like.pdf'
    encrypted = root / 'encrypted.pdf'

    make_text_pdf(normal, TEXT_BODY)
    shutil.copyfile(normal, unicode_pdf)
    corrupt.write_bytes(b'%PDF-1.4\nthis is not a valid pdf xref\n%%EOF')
    make_scan_like_pdf(scan_like)
    make_encrypted_pdf(normal, encrypted)
    return {
        normal.name: normal,
        unicode_pdf.name: unicode_pdf,
        corrupt.name: corrupt,
        scan_like.name: scan_like,
        encrypted.name: encrypted,
    }


def make_text_pdf(path: Path, text: str) -> None:
    import fitz  # type: ignore

    document = fitz.open()
    page = document.new_page(width=595, height=842)
    page.insert_text((72, 72), text, fontsize=12)
    document.save(path)
    document.close()


def make_scan_like_pdf(path: Path) -> None:
    import fitz  # type: ignore

    document = fitz.open()
    page = document.new_page(width=595, height=842)
    page.draw_rect(fitz.Rect(72, 72, 420, 240), color=(0.1, 0.1, 0.1), fill=(0.92, 0.92, 0.92))
    page.draw_rect(fitz.Rect(96, 104, 396, 128), color=(0.3, 0.3, 0.3), fill=(0.3, 0.3, 0.3))
    page.draw_rect(fitz.Rect(96, 148, 360, 172), color=(0.3, 0.3, 0.3), fill=(0.3, 0.3, 0.3))
    document.save(path)
    document.close()


def make_encrypted_pdf(source: Path, destination: Path) -> None:
    reader = PdfReader(str(source))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt('secret')
    with destination.open('wb') as handle:
        writer.write(handle)


def run_parser_case(name: str, path: Path) -> dict:
    settings = get_settings()
    parser = PdfParser()
    try:
        pages, warning = parser.parse(str(path))
        chunks = Chunker(settings).chunk(pages, str(uuid.uuid4()), str(uuid.uuid4()), path.name)
        status = 'completed' if chunks else 'failed'
        error = None if chunks else (warning or 'No chunks created')
        return {
            'case': name,
            'status': status,
            'pages': len(pages),
            'extracted_text_length': sum(len(page.text) for page in pages),
            'chunks': len(chunks),
            'parser_used': parser.last_report.get('parser_used'),
            'warning': warning,
            'error_message': error,
        }
    except Exception as error:
        return {
            'case': name,
            'status': 'failed',
            'pages': parser.last_report.get('total_pages', 0),
            'extracted_text_length': parser.last_report.get('extracted_text_length', 0),
            'chunks': 0,
            'parser_used': parser.last_report.get('parser_used'),
            'warning': parser.last_report.get('warning'),
            'error_message': f'{error.__class__.__name__}: {error}',
        }


def run_api_ingest(api_url: str, case_name: str, path: Path) -> dict:
    import requests

    document_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    response = requests.post(
        f'{api_url}/documents/ingest',
        json={
            'user_id': user_id,
            'document_id': document_id,
            'file_path': str(path),
            'file_name': path.name,
        },
        timeout=120,
    )
    data = response.json()
    return {
        'case': case_name,
        'http_status': response.status_code,
        'document_id': document_id,
        'status': data.get('status'),
        'total_pages': data.get('total_pages'),
        'extracted_text_length': data.get('extracted_text_length'),
        'total_chunks': data.get('total_chunks'),
        'parser_used': data.get('parser_used'),
        'error_message': data.get('error_message'),
        'chunk_report_path': data.get('chunk_report_path'),
    }


def assert_case(results: list[dict], name: str, status: str, chunks_gt: int | None = None, error_contains: str | None = None, warning_contains: str | None = None) -> None:
    item = next(result for result in results if result['case'] == name)
    assert item['status'] == status, item
    if chunks_gt is not None:
        assert item.get('chunks', item.get('total_chunks', 0)) > chunks_gt, item
    if error_contains:
        assert error_contains in (item.get('error_message') or ''), item
    if warning_contains:
        assert warning_contains in (item.get('warning') or item.get('error_message') or ''), item


def safe_print(message: str) -> None:
    encoding = sys.stdout.encoding or 'utf-8'
    print(message.encode(encoding, errors='backslashreplace').decode(encoding, errors='replace'))


if __name__ == '__main__':
    main()
