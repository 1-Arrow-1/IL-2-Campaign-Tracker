"""Logging helpers for IL-2 Campaign Tracker."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


# Mapping of Unicode characters to ASCII-safe equivalents
UNICODE_TO_ASCII = {
    '✓': '[OK]',
    '✅': '[OK]',
    '❌': '[ERROR]',
    '⚠️': '[WARN]',
    '⚠': '[WARN]',
    '🎮': '[GAME]',
    '👋': '[BYE]',
    '🛑': '[STOP]',
    '📝': '[FILE]',
    '📋': '[LIST]',
    '📖': '[READ]',
    '📁': '[DIR]',
    '🔄': '[SYNC]',
    '⚡': '[FAST]',
    '🎯': '[TARGET]',
    '🚀': '[START]',
    '🟢': '[ON]',
    '🟡': '[!]',
    '💾': '[SAVE]',
    '🔹': '[*]',
    '🔁': '[LOOP]',
}


class SafeStreamHandler(logging.StreamHandler):
    """StreamHandler that gracefully handles Unicode encoding errors on Windows console."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            super().emit(record)
        except UnicodeEncodeError:
            # Replace problematic Unicode characters and retry
            original_msg = record.msg
            if isinstance(original_msg, str):
                safe_msg = original_msg
                for unicode_char, ascii_replacement in UNICODE_TO_ASCII.items():
                    safe_msg = safe_msg.replace(unicode_char, ascii_replacement)
                # Replace any remaining non-ASCII with '?'
                safe_msg = safe_msg.encode('ascii', errors='replace').decode('ascii')
                record.msg = safe_msg
                try:
                    super().emit(record)
                except Exception:
                    pass  # Silently fail if still can't emit
                finally:
                    record.msg = original_msg  # Restore original message
            else:
                pass  # Can't fix non-string messages


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

    # Use SafeStreamHandler to handle Unicode encoding errors on Windows
    console_handler = SafeStreamHandler(sys.stdout)
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
