import json
from pathlib import Path
from app.config import Settings


class ReportService:
    def __init__(self, settings: Settings):
        self.base = Path(settings.debug_report_path)
        self.base.mkdir(parents=True, exist_ok=True)

    def write(self, name: str, data: dict) -> str:
        path = self.base / name
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        return str(path)

    def read(self, path_or_name: str) -> dict:
        path = Path(path_or_name)
        if not path.is_absolute():
            path = self.base / path_or_name
        return json.loads(path.read_text(encoding='utf-8'))
