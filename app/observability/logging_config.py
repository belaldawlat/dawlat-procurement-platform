"""Production-safe structured logging configuration."""

from __future__ import annotations

import json
import logging
import logging.handlers
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.observability.log_context import get_log_context
from app.observability.redaction import redact_mapping


_STANDARD_LOG_RECORD_FIELDS = frozenset(
    logging.makeLogRecord({}).__dict__.keys()
)


class StructuredJsonFormatter(logging.Formatter):
    """Render Python log records as safe JSON documents."""

    def format(self, record: logging.LogRecord) -> str:
        """Return a redacted JSON representation of a log record."""

        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        context = get_log_context().as_dict()

        if context:
            payload["context"] = redact_mapping(context)

        extras = {
            key: self._serialise(value)
            for key, value in record.__dict__.items()
            if key not in _STANDARD_LOG_RECORD_FIELDS
            and key not in {
                "message",
                "asctime",
            }
        }

        if extras:
            payload["data"] = redact_mapping(extras)

        if record.exc_info:
            payload["exception"] = self.formatException(
                record.exc_info
            )

        return json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )

    @staticmethod
    def _serialise(value: Any) -> Any:
        """Convert common objects into JSON-safe values."""

        if is_dataclass(value) and not isinstance(value, type):
            return asdict(value)

        if isinstance(value, Path):
            return str(value)

        return value


def configure_logging(
    *,
    level: int | str = logging.INFO,
    log_directory: str | Path = "logs",
    enable_console: bool = True,
    enable_file: bool = True,
    file_name: str = "application.jsonl",
    max_bytes: int = 10_000_000,
    backup_count: int = 10,
) -> logging.Logger:
    """Configure enterprise application logging."""

    resolved_level = logging.getLevelName(level)

    if isinstance(resolved_level, str):
        numeric_level = logging._nameToLevel.get(
            resolved_level.upper(),
            logging.INFO,
        )
    else:
        numeric_level = int(resolved_level)

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        handler.close()

    formatter = StructuredJsonFormatter()

    if enable_console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    if enable_file:
        directory = Path(log_directory)
        directory.mkdir(parents=True, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            directory / file_name,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    logging.captureWarnings(True)

    logger = logging.getLogger("dawlat.observability")
    logger.info(
        "Enterprise logging configured.",
        extra={
            "event_type": "logging_configured",
            "console_enabled": enable_console,
            "file_enabled": enable_file,
        },
    )

    return logger


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced application logger."""

    cleaned_name = str(name or "application").strip()

    return logging.getLogger(f"dawlat.{cleaned_name}")