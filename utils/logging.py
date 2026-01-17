"""Logging helpers for IL-2 Campaign Tracker."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def get_logger(name: str, log_path: str | Path | None = None, debug: bool = False) -> logging.Logger:
    """Return a configured logger with rotating file + console handlers."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    resolved_path = Path(log_path).expanduser().resolve() if log_path else None

    formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

    if resolved_path:
        file_handler = RotatingFileHandler(
            resolved_path,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding='utf-8',
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


def log_message(
    logger: logging.Logger,
    *args: object,
    sep: str = " ",
    end: str = "\n",
    flush: bool = False,
    level: str | None = None,
) -> None:
    """Log a message with print-like semantics using the provided logger."""
    message = sep.join(str(arg) for arg in args)
    _ = (end, flush)

    if level is None:
        lowered = message.lower()
        if message.startswith("❌") or lowered.startswith("error") or "[error]" in lowered:
            level = "error"
        elif (
            message.startswith("⚠️")
            or "warning" in lowered
            or "[warn]" in lowered
            or "[warning]" in lowered
        ):
            level = "warning"
        elif (
            message.startswith("[debug]")
            or lowered.startswith("debug")
            or "[debug]" in lowered
        ):
            level = "debug"
        else:
            level = "info"

    log_fn = getattr(logger, level, logger.info)
    log_fn(message)


def log_info(logger: logging.Logger, *args: object) -> None:
    """Log an informational message."""
    log_message(logger, *args, level="info")


def log_warning(logger: logging.Logger, *args: object) -> None:
    """Log a warning message."""
    log_message(logger, *args, level="warning")


def log_error(logger: logging.Logger, *args: object) -> None:
    """Log an error message."""
    log_message(logger, *args, level="error")


def log_success(logger: logging.Logger, *args: object) -> None:
    """Log a success message with a checkmark prefix."""
    if args:
        message = "✅ " + " ".join(str(arg) for arg in args)
    else:
        message = "✅"
    log_message(logger, message, level="info")


def log_section_header(logger: logging.Logger, title: str) -> None:
    """Log a section header with divider lines."""
    divider = "=" * 60
    log_message(logger, divider, level="info")
    log_message(logger, title, level="info")
    log_message(logger, divider, level="info")