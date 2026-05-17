import json
import mimetypes
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from app.core.logging import get_logger
from app.models.schemas import PageText

logger = get_logger(__name__)


class PdfParser:
    def __init__(self) -> None:
        self.last_report: dict[str, Any] = {}

    def parse(self, file_path: str) -> tuple[list[PageText], str | None]:
        path = Path(file_path).expanduser()
        self.last_report = self._base_report(path)
        self._log('parse_start', self.last_report)

        if path.suffix.lower() != '.pdf':
            self.last_report['error_message'] = 'Only PDF files are allowed'
            raise ValueError('Only PDF files are allowed')

        if not path.exists():
            self.last_report['error_message'] = 'PDF file does not exist'
            self._log('file_missing', self.last_report)
            raise FileNotFoundError(f'PDF file does not exist: {path}')

        if not path.is_file():
            self.last_report['error_message'] = 'PDF path is not a file'
            self._log('not_a_file', self.last_report)
            raise ValueError(f'PDF path is not a file: {path}')

        size = path.stat().st_size
        self.last_report['file_size'] = size
        if size <= 0:
            self.last_report['error_message'] = 'PDF file is empty'
            self._log('empty_file', self.last_report)
            raise ValueError(f'PDF file is empty: {path}')

        pypdf_pages: list[PageText] = []
        pypdf_error: str | None = None
        try:
            pypdf_pages = self._parse_with_pypdf(path)
        except Exception as error:
            pypdf_error = self._error_text(error)
            self.last_report.setdefault('parser_errors', []).append({'parser': 'pypdf', 'error': pypdf_error})
            self._log('pypdf_failed', {'file_path': str(path), 'error': pypdf_error})

        pages = pypdf_pages
        parser_used = 'pypdf' if pypdf_pages else None
        pypdf_text_length = self._text_length(pypdf_pages)

        if pypdf_error or pypdf_text_length == 0:
            try:
                pymupdf_pages = self._parse_with_pymupdf(path)
                pymupdf_text_length = self._text_length(pymupdf_pages)
                if not pages or pymupdf_text_length >= pypdf_text_length:
                    pages = pymupdf_pages
                    parser_used = 'pymupdf'
            except ImportError as error:
                message = self._error_text(error)
                self.last_report.setdefault('parser_errors', []).append({'parser': 'pymupdf', 'error': message})
                self._log('pymupdf_unavailable', {'file_path': str(path), 'error': message})
            except Exception as error:
                message = self._error_text(error)
                self.last_report.setdefault('parser_errors', []).append({'parser': 'pymupdf', 'error': message})
                self._log('pymupdf_failed', {'file_path': str(path), 'error': message})

        text_length = self._text_length(pages)
        parser_errors = self.last_report.get('parser_errors') or []
        if not pages and parser_errors:
            detail = '; '.join(f"{item['parser']}: {item['error']}" for item in parser_errors)
            self.last_report['error_message'] = f'PDF parser failed: {detail}'
            self._log('parse_failed', self.last_report)
            raise ValueError(self.last_report['error_message'])

        warning = None
        if pages and text_length == 0:
            warning = 'PDF scan/image-only: no text layer found; OCR is required.'
            self.last_report['is_scan_or_image_only'] = True
            self.last_report['warning'] = warning

        self.last_report.update({
            'parser_used': parser_used,
            'total_pages': len(pages),
            'extracted_text_length': text_length,
            'empty_pages': sum(1 for page in pages if not page.text.strip()),
        })
        self._log('parse_complete', self.last_report)
        return pages, warning

    def _parse_with_pypdf(self, path: Path) -> list[PageText]:
        reader = PdfReader(str(path), strict=False)
        if reader.is_encrypted:
            self.last_report['encrypted'] = True
            decrypt_result = 0
            try:
                decrypt_result = reader.decrypt('')
            except Exception as error:
                raise ValueError(f'PDF is encrypted/password protected; password is required. {self._error_text(error)}') from error
            if not decrypt_result:
                raise ValueError('PDF is encrypted/password protected; password is required.')

        page_count = len(reader.pages)
        self.last_report['pypdf_page_count'] = page_count
        pages: list[PageText] = []
        cursor = 0
        for index, page in enumerate(reader.pages, start=1):
            try:
                raw = page.extract_text() or ''
            except Exception as error:
                self.last_report.setdefault('page_errors', []).append({
                    'parser': 'pypdf',
                    'page_number': index,
                    'error': self._error_text(error),
                })
                raw = ''
            text = self.clean(raw)
            pages.append(PageText(page_number=index, text=text, char_start=cursor, char_end=cursor + len(text)))
            cursor += len(text) + 1
        return pages

    def _parse_with_pymupdf(self, path: Path) -> list[PageText]:
        try:
            import fitz  # type: ignore
        except ImportError as error:
            raise ImportError('PyMuPDF is not installed; install pymupdf for PDF fallback parsing.') from error

        with fitz.open(stream=path.read_bytes(), filetype='pdf') as document:
            if document.needs_pass:
                self.last_report['encrypted'] = True
                raise ValueError('PDF is encrypted/password protected; password is required.')
            self.last_report['pymupdf_page_count'] = document.page_count
            pages: list[PageText] = []
            cursor = 0
            for index in range(document.page_count):
                try:
                    raw = document.load_page(index).get_text('text') or ''
                except Exception as error:
                    self.last_report.setdefault('page_errors', []).append({
                        'parser': 'pymupdf',
                        'page_number': index + 1,
                        'error': self._error_text(error),
                    })
                    raw = ''
                text = self.clean(raw)
                pages.append(PageText(page_number=index + 1, text=text, char_start=cursor, char_end=cursor + len(text)))
                cursor += len(text) + 1
            return pages

    def clean(self, text: str) -> str:
        lines = [' '.join(line.split()) for line in text.splitlines()]
        cleaned = []
        previous_blank = False
        for line in lines:
            blank = not line
            if blank and previous_blank:
                continue
            if line:
                cleaned.append(line)
            previous_blank = blank
        return '\n'.join(cleaned).strip()

    def _base_report(self, path: Path) -> dict[str, Any]:
        mime_type, _ = mimetypes.guess_type(path.name)
        return {
            'file_name': path.name,
            'file_path': str(path),
            'file_size': None,
            'mime_type': mime_type or 'application/pdf',
            'parser_used': None,
            'total_pages': 0,
            'extracted_text_length': 0,
            'empty_pages': 0,
            'encrypted': False,
            'is_scan_or_image_only': False,
            'parser_errors': [],
            'page_errors': [],
            'warning': None,
            'error_message': None,
        }

    def _text_length(self, pages: list[PageText]) -> int:
        return sum(len(page.text) for page in pages)

    def _error_text(self, error: Exception) -> str:
        return f'{error.__class__.__name__}: {error}'

    def _log(self, event: str, data: dict[str, Any]) -> None:
        logger.info('pdf_parser %s %s', event, json.dumps(data, ensure_ascii=False, default=str))
