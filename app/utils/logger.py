"""
Structured logging setup.

We use Python's standard logging module with a JSON-ish structured
formatter so logs are easy to parse in aggregation tools. We deliberately
avoid logging secrets, tokens, or full webhook URLs with credentials.
"""
import logging
import sys
from typing import Any

from app.config import get_settings


class StructuredFormatter(logging.Formatter):
    """Formats log records as a single-line key=value structured string."""

    def format(self, record: logging.LogRecord) -> str:
        base = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Merge any extra fields passed via `extra={...}`
        reserved = {
            "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
            "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
            "created", "msecs", "relativeCreated", "thread", "threadName",
            "processName", "process", "message", "taskName",
        }
        for key, value in record.__dict__.items():
            if key not in reserved and not key.startswith("_"):
                base[key] = value

        parts = [f'{k}="{v}"' if isinstance(v, str) else f"{k}={v}" for k, v in base.items()]
        return " ".join(parts)


def configure_logging() -> None:
    settings = get_settings()
    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())

    # Avoid duplicate handlers on reload
    root.handlers.clear()
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
