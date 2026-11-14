"""Structured logging setup with file rotation for SeniorVoice pipeline."""

import logging
import sys
from logging.handlers import RotatingFileHandler

from config import LOG_LEVEL, LOG_DIR, LOG_MAX_BYTES, LOG_BACKUP_COUNT, LOG_CONTENT

_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_initialized = False

# Name of the logger for conversation content. It never reaches the log file.
CONTENT_LOGGER = "seniorvoice.content"


class _NoContentFilter(logging.Filter):
    """Safety net: drop records from the content logger on file handlers."""

    def filter(self, record: logging.LogRecord) -> bool:
        return not record.name.startswith(CONTENT_LOGGER)


def setup_logging() -> None:
    """Configure root logger with console + rotating file handlers."""
    global _initialized
    if _initialized:
        return
    _initialized = True

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / "pipeline.log"

    root = logging.getLogger()
    root.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    formatter = logging.Formatter(_FORMAT, datefmt=_DATE_FORMAT)

    # Console handler (stdout)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    # Rotating file handler
    file_handler = RotatingFileHandler(
        log_file, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(_NoContentFilter())
    root.addHandler(file_handler)

    _setup_content_logger(formatter)


def _setup_content_logger(formatter: logging.Formatter) -> None:
    """Content logger: console only, and only when LOG_CONTENT=true."""
    content = logging.getLogger(CONTENT_LOGGER)
    content.propagate = False  # never reaches the root file handler
    content.handlers.clear()
    if LOG_CONTENT:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        content.addHandler(handler)
        content.setLevel(logging.DEBUG)
    else:
        content.addHandler(logging.NullHandler())
        content.setLevel(logging.CRITICAL + 1)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger. Call setup_logging() first in main.

    Never pass conversation content (user or assistant text) to this logger;
    use get_content_logger() for that.
    """
    return logging.getLogger(name)


def get_content_logger(name: str) -> logging.Logger:
    """Logger for conversation content. Console only and off by default (A8)."""
    content = logging.getLogger(f"{CONTENT_LOGGER}.{name}")
    root_content = logging.getLogger(CONTENT_LOGGER)
    if not _initialized:
        # Before setup_logging(): make sure content cannot propagate anywhere.
        root_content.propagate = False
        if not root_content.handlers:
            root_content.addHandler(logging.NullHandler())
            root_content.setLevel(logging.CRITICAL + 1)
    return content
