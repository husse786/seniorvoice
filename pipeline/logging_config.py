"""Structured logging setup with file rotation for SeniorVoice pipeline."""

import logging
import sys
from logging.handlers import RotatingFileHandler

from config import LOG_LEVEL, LOG_DIR, LOG_MAX_BYTES, LOG_BACKUP_COUNT

_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_initialized = False


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
    root.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger. Call setup_logging() first in main."""
    return logging.getLogger(name)
