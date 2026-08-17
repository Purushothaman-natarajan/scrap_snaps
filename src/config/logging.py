"""Structured logging configuration using structlog."""

import logging
import os
import sys
from typing import Any

import structlog
from structlog.types import EventDict, Processor

from src.config.settings import settings


def add_service_name(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Add service name to all log entries."""
    event_dict["service"] = "scrap-snaps"
    return event_dict


def filter_sensitive_data(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Filter out sensitive data from logs."""
    sensitive_keys = {"api_key", "password", "secret", "token", "authorization"}
    for key in list(event_dict.keys()):
        if any(sensitive in key.lower() for sensitive in sensitive_keys):
            event_dict[key] = "[REDACTED]"
    return event_dict


def configure_logging(
    level: str | None = None,
    json_format: bool | None = None,
    include_timestamp: bool | None = None,
) -> None:
    """Configure structlog for structured logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR). Defaults to settings.
        json_format: Whether to output JSON. Defaults to settings.
        include_timestamp: Whether to include timestamps. Defaults to settings.
    """
    log_level = level or settings.log_level
    json_logs = json_format if json_format is not None else settings.log_json
    timestamps = (
        include_timestamp if include_timestamp is not None
        else settings.log_timestamp
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    root_logger.addHandler(console_handler)

    # File handler for detailed capture
    if settings.log_capture:
        log_dir = os.path.dirname(settings.log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        file_handler = logging.FileHandler(settings.log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)  # Capture everything to file
        file_formatter = logging.Formatter("%(message)s")
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    # Shared processors
    shared_processors: list[Processor] = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        add_service_name,
        filter_sensitive_data,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if timestamps:
        shared_processors.append(structlog.processors.TimeStamper(fmt="iso", utc=True))

    if json_logs:
        processors = shared_processors + [
            structlog.processors.JSONRenderer(),
        ]
    else:
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name (typically __name__). If None, uses caller's module.

    Returns:
        Configured structlog logger.
    """
    return structlog.get_logger(name)


# Configure on module import
configure_logging()
