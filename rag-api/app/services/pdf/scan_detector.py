from app.models.schemas import PageText


class ScanDetector:
    def is_scan_or_image_only(self, pages: list[PageText]) -> bool:
        return bool(pages) and sum(len(page.text.strip()) for page in pages) == 0
