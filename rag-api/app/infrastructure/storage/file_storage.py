from pathlib import Path


class FileStorage:
    def resolve_existing_file(self, file_path: str) -> Path:
        path = Path(file_path).expanduser()
        if not path.exists():
            raise FileNotFoundError(f'PDF file does not exist: {path}')
        if not path.is_file():
            raise ValueError(f'PDF path is not a file: {path}')
        if path.stat().st_size <= 0:
            raise ValueError(f'PDF file is empty: {path}')
        return path
