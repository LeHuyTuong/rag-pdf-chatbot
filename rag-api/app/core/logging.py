import logging
import sys


class SafeStreamHandler(logging.StreamHandler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
            encoding = getattr(self.stream, 'encoding', None) or 'utf-8'
            safe_message = message.encode(encoding, errors='backslashreplace').decode(encoding, errors='replace')
            self.stream.write(safe_message + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)


def configure_logging() -> None:
    handler = SafeStreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s [%(name)s] %(message)s'))
    logging.basicConfig(
        level=logging.INFO,
        handlers=[handler],
        force=True,
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
