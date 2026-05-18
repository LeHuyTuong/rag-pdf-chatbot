from app.models.schemas import PageText
from app.services.pdf.pdf_parser import PdfParser


class PdfTextExtractor:
    """
    Wrapper nhẹ cho `PdfParser` để cung cấp API thống nhất khi cần.

    Hiện tại chỉ gọi `PdfParser.parse` và trả về (pages, warning).
    """
    def __init__(self, parser: PdfParser | None = None):
        self.parser = parser or PdfParser()

    def extract(self, file_path: str) -> tuple[list[PageText], str | None]:
        """
        Trả về (pages, warning) giống `PdfParser.parse`.
        """
        return self.parser.parse(file_path)
