from app.models.schemas import PageText
from app.services.pdf.pdf_parser import PdfParser


class PdfTextExtractor:
    def __init__(self, parser: PdfParser | None = None):
        self.parser = parser or PdfParser()

    def extract(self, file_path: str) -> tuple[list[PageText], str | None]:
        return self.parser.parse(file_path)
