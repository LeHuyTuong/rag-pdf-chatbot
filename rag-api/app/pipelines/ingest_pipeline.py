"""
Pipeline xử lý ingest tài liệu PDF vào hệ thống RAG.

Luồng chính:
1. Gọi `PdfParser.parse` để đọc và trích xuất văn bản từng trang.
2. Gọi `Chunker.chunk` để tách văn bản thành các chunk theo cấu hình CHUNK_SIZE/CHUNK_OVERLAP.
3. Gọi `QdrantService.upsert_chunks` để sinh embedding và upsert vector vào Qdrant.
4. Lưu metadata/chunks vào MySQL (nếu có) và tạo báo cáo (chunk report).

Ghi chú quan trọng:
- Đoạn code này chỉ orchestration; không thực hiện background job (TODO: cân nhắc chuyển ingest lớn sang job bất đồng bộ).
- Nếu chunker trả về rỗng hoặc parser báo PDF không có text layer, pipeline sẽ trả về IngestResponse báo lỗi/warning.
"""

from typing import Any

from app.core.config import Settings
from app.core.logging import get_logger
from app.infrastructure.mysql.mysql_service import MySqlService
from app.infrastructure.qdrant.qdrant_service import QdrantService
from app.models.schemas import IngestRequest, IngestResponse, utc_now
from app.services.chunking.chunker import Chunker
from app.services.embedding.embedding_service import EmbeddingService
from app.services.pdf.pdf_parser import PdfParser
from app.services.reports.chunk_report_service import ChunkReportService

logger = get_logger(__name__)


class IngestPipeline:
    """
    Lớp điều phối quá trình ingest cho một PDF đơn lẻ.

    Mục đích: đảm bảo chuỗi hành động parse -> chunk -> embed -> upsert -> persist và ghi report.
    """
    def __init__(self, settings: Settings):
        self.settings = settings
        self.mysql = MySqlService(settings)
        self.reports = ChunkReportService(settings)

    def ingest(self, request: IngestRequest) -> IngestResponse:
        """
        Thực hiện ingest cho `request` mô tả file đã upload.

        Trả về `IngestResponse` với các trường: status, total_pages, total_chunks, chunk_report_path, ...

        Quy tắc lựa chọn/edge-cases:
        - Nếu parser phát hiện PDF là scan (không có text layer) thì `warning` sẽ được truyền trong report.
        - Nếu không có chunk hợp lệ, phương thức trả về status='failed' và kèm message chi tiết.
        """
        parser = PdfParser()
        pages = []
        chunks = []
        warning = None
        status = 'failed'
        error_message = None

        try:
            logger.info(
                'ingest start document_id=%s user_id=%s file_name=%s file_path=%s',
                request.document_id,
                request.user_id,
                request.file_name,
                request.file_path,
            )
            pages, warning = parser.parse(request.file_path)
            text_length = sum(len(page.text) for page in pages)
            logger.info(
                'ingest extracted document_id=%s pages=%s extracted_text_length=%s parser=%s',
                request.document_id,
                len(pages),
                text_length,
                parser.last_report.get('parser_used'),
            )

            chunks = Chunker(self.settings).chunk(pages, request.document_id, request.user_id, request.file_name)
            logger.info('ingest chunked document_id=%s chunks=%s', request.document_id, len(chunks))

            if not chunks:
                error_message = self._empty_chunk_error(text_length, pages, warning)
                report_path = self._write_report(request, parser.last_report, pages, chunks, status, warning, error_message, [])
                return IngestResponse(
                    document_id=request.document_id,
                    status=status,
                    total_pages=len(pages),
                    total_chunks=0,
                    chunk_report_path=report_path,
                    extracted_text_length=text_length,
                    parser_used=parser.last_report.get('parser_used'),
                    error_message=error_message,
                    warning=warning,
                    chunks=[],
                )

            qdrant = QdrantService(self.settings, EmbeddingService(self.settings))
            chunks = qdrant.upsert_chunks(chunks)
            persistence_warnings = self._persist_chunks(chunks)

            status = 'completed'
            report_path = self._write_report(request, parser.last_report, pages, chunks, status, warning, None, persistence_warnings)
            return IngestResponse(
                document_id=request.document_id,
                status=status,
                total_pages=len(pages),
                total_chunks=len(chunks),
                chunk_report_path=report_path,
                extracted_text_length=sum(len(page.text) for page in pages),
                parser_used=parser.last_report.get('parser_used'),
                error_message=None,
                warning=warning,
                chunks=chunks,
            )
        except Exception as error:
            error_message = f'{error.__class__.__name__}: {error}'
            logger.exception('ingest failed document_id=%s error=%s', request.document_id, error_message)
            report_path = self._write_report(request, parser.last_report, pages, chunks, status, warning, error_message, [])
            return IngestResponse(
                document_id=request.document_id,
                status=status,
                total_pages=len(pages) or int(parser.last_report.get('total_pages') or 0),
                total_chunks=len(chunks),
                chunk_report_path=report_path,
                extracted_text_length=int(parser.last_report.get('extracted_text_length') or 0),
                parser_used=parser.last_report.get('parser_used'),
                error_message=error_message,
                warning=warning or parser.last_report.get('warning'),
                chunks=[],
            )

    def get_chunks(self, document_id: str) -> list[dict]:
        self.mysql.init_schema()
        return self.mysql.get_chunks(document_id)

    def _persist_chunks(self, chunks) -> list[str]:
        try:
            self.mysql.init_schema()
            self.mysql.save_chunks(chunks)
            return []
        except Exception as error:
            message = f'MySQL chunk persistence failed: {error.__class__.__name__}: {error}'
            logger.warning(message)
            return [message]

    def _empty_chunk_error(self, text_length: int, pages: list, warning: str | None) -> str:
        if text_length == 0 and pages:
            return warning or 'PDF has pages but no extractable text layer; OCR is required.'
        if text_length == 0:
            return 'PDF parser returned no extractable text.'
        return 'Text was extracted but chunker returned 0 chunks; check chunking configuration.'

    def _write_report(
        self,
        request: IngestRequest,
        parse_report: dict[str, Any],
        pages: list,
        chunks: list,
        status: str,
        warning: str | None,
        error_message: str | None,
        persistence_warnings: list[str],
    ) -> str:
        parser_info = parse_report or {}
        extracted_text_length = sum(len(page.text) for page in pages) if pages else int(parser_info.get('extracted_text_length') or 0)
        report = {
            'document_id': request.document_id,
            'user_id': request.user_id,
            'file_name': request.file_name,
            'file_path': request.file_path,
            'file_size': parser_info.get('file_size'),
            'mime_type': parser_info.get('mime_type'),
            'status': status,
            'total_pages': len(pages) or int(parser_info.get('total_pages') or 0),
            'extracted_text_length': extracted_text_length,
            'total_chunks': len(chunks),
            'parser_used': parser_info.get('parser_used'),
            'encrypted': parser_info.get('encrypted', False),
            'is_scan_or_image_only': parser_info.get('is_scan_or_image_only', False),
            'empty_pages': parser_info.get('empty_pages', 0),
            'warning': warning or parser_info.get('warning'),
            'error_message': error_message or parser_info.get('error_message'),
            'parser_errors': parser_info.get('parser_errors', []),
            'page_errors': parser_info.get('page_errors', []),
            'persistence_warnings': persistence_warnings,
            'chunking_config': {
                'strategy': 'page_aware_token_window',
                'chunk_size': self.settings.chunk_size,
                'chunk_overlap': self.settings.chunk_overlap,
            },
            'chunks': [
                {
                    'chunk_id': chunk.chunk_id,
                    'chunk_index': chunk.chunk_index,
                    'page_start': chunk.page_start,
                    'page_end': chunk.page_end,
                    'char_start': chunk.char_start,
                    'char_end': chunk.char_end,
                    'token_count': chunk.token_count,
                    'chunk_reason': chunk.chunk_reason,
                    'preview': chunk.content[:240],
                }
                for chunk in chunks
            ],
            'created_at': utc_now(),
        }
        path = self.reports.write(f'chunk_report_{request.document_id}.json', report)
        logger.info(
            'ingest report document_id=%s status=%s pages=%s text=%s chunks=%s parser=%s path=%s',
            request.document_id,
            status,
            report['total_pages'],
            extracted_text_length,
            len(chunks),
            report['parser_used'],
            path,
        )
        return path
