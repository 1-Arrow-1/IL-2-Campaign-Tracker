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
