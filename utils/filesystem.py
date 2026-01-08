from pathlib import Path


def is_file_locked(path: Path) -> bool:
    """True if the file exists and is locked for writing (e.g., open in a PDF viewer on Windows)."""
    if not path.exists():
        return False
    try:
        with open(path, "ab"):
            return False
    except (PermissionError, OSError):
        return True
