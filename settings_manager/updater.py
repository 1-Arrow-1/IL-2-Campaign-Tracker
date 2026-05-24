"""
IL-2 Campaign Tracker - Update Installer

Handles in-place update from a downloaded zip file:
  - Parses update zip and reads optional manifest (version info, description)
  - Detects running tracker processes that would block file replacement
  - Creates a timestamped backup zip of all files about to be overwritten
  - Copies files atomically (write to .tmp then rename)
  - Protects user-data files from being overwritten
  - Writes a human-readable install log
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Files that must NEVER be overwritten by an update (user config / data).
_PROTECTED_FILES: frozenset[str] = frozenset({
    "campaign_tracker_settings.json",
    "campaign_progress_config.yaml",
    "campaign_mission_dates.json",
    "stock_campaigns.yaml",
    "update_log.txt",
})

# Directory prefixes (relative, forward-slash normalised) that must not be touched.
_PROTECTED_DIR_PREFIXES: tuple[str, ...] = (
    "data/",
    "story_data/",
    "reports/",
    "backups/",
)

# Tracker executables to check before installing (cannot overwrite running EXEs).
TRACKER_EXES: tuple[str, ...] = (
    "IL2_CampaignTracker_v2.2_ML.exe",
    "Career_Service_Record.exe",
    "Campaign_Service_Record.exe",
    # IL2_Settings_Manager.exe is intentionally absent — it can update itself
    # by deferring its own exe to a .pending file (applied on restart).
)

# Manifest filename inside the update zip (optional but recommended).
_MANIFEST_FILENAME = "update_manifest.json"

# Version file in the install directory.
_VERSION_FILENAME = "version.txt"

# Sentinel written when a .pending restart is needed; deleted after apply.
RESTART_PENDING_FILENAME = "_restart_pending.json"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class UpdateManifest:
    version: str = ""
    description: str = ""
    min_version: str = ""


@dataclass
class FileEntry:
    zip_path: str       # path as stored inside the zip
    dest_path: str      # relative path for the install dir (OS separators)
    is_new: bool        # True = file doesn't exist yet; False = will overwrite
    is_protected: bool  # True = will be skipped to preserve user data
    size: int = 0       # uncompressed size in bytes


@dataclass
class InstallResult:
    success: bool = False
    installed: List[str] = field(default_factory=list)
    skipped_protected: List[str] = field(default_factory=list)
    failed: List[Tuple[str, str]] = field(default_factory=list)  # (path, error)
    pending_restart: List[str] = field(default_factory=list)     # written as .pending; need restart
    backup_path: Optional[str] = None
    error: str = ""


# ---------------------------------------------------------------------------
# Version helpers
# ---------------------------------------------------------------------------

def read_current_version(base_dir: Path) -> str:
    """Return the installed version string, or empty string if unknown."""
    vf = base_dir / _VERSION_FILENAME
    if vf.exists():
        try:
            return vf.read_text(encoding="utf-8").strip()
        except OSError:
            pass
    return ""


# ---------------------------------------------------------------------------
# Zip parsing
# ---------------------------------------------------------------------------

def parse_zip(
    zip_path: Path,
    base_dir: Path,
) -> Tuple[Optional[UpdateManifest], List[FileEntry], str]:
    """
    Open and inspect *zip_path*.

    Returns (manifest, file_entries, error_message).
    On failure returns (None, [], error_message).
    """
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()

            # --- read manifest ---
            manifest = UpdateManifest()
            if _MANIFEST_FILENAME in names:
                try:
                    raw = zf.read(_MANIFEST_FILENAME).decode("utf-8")
                    data = json.loads(raw)
                    manifest.version = str(data.get("version") or "").strip()
                    manifest.description = str(data.get("description") or "").strip()
                    manifest.min_version = str(data.get("min_version") or "").strip()
                except Exception:
                    pass  # malformed manifest — treat as empty

            # --- enumerate files ---
            entries: list[FileEntry] = []
            for name in names:
                if name == _MANIFEST_FILENAME:
                    continue
                if name.endswith("/") or name.endswith("\\"):
                    continue  # directory entry

                dest = name.replace("/", os.sep)
                info = zf.getinfo(name)
                entries.append(FileEntry(
                    zip_path=name,
                    dest_path=dest,
                    is_new=not (base_dir / dest).exists(),
                    is_protected=_is_protected(dest),
                    size=info.file_size,
                ))

            return manifest, entries, ""

    except zipfile.BadZipFile:
        return None, [], "Not a valid zip file."
    except Exception as exc:
        return None, [], str(exc)


def _is_protected(dest_path: str) -> bool:
    """Return True if this path must not be overwritten."""
    filename = os.path.basename(dest_path).lower()
    if filename in {f.lower() for f in _PROTECTED_FILES}:
        return True
    normalised = dest_path.replace("\\", "/").lower()
    for prefix in _PROTECTED_DIR_PREFIXES:
        if normalised.startswith(prefix):
            return True
    return False


# ---------------------------------------------------------------------------
# Process detection
# ---------------------------------------------------------------------------

def detect_running_trackers() -> List[str]:
    """Return names of tracker EXEs that are currently running."""
    running: list[str] = []
    try:
        import psutil
        running_lower = {
            p.info["name"].lower()
            for p in psutil.process_iter(["name"])
            if p.info.get("name")
        }
        for exe in TRACKER_EXES:
            if exe.lower() in running_lower:
                running.append(exe)
    except ImportError:
        for exe in TRACKER_EXES:
            try:
                result = subprocess.run(
                    ["tasklist", "/FI", f"IMAGENAME eq {exe}", "/NH"],
                    capture_output=True,
                    text=True,
                    creationflags=(
                        subprocess.CREATE_NO_WINDOW
                        if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
                    ),
                )
                if exe.lower() in result.stdout.lower():
                    running.append(exe)
            except Exception:
                pass
    return running


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------

def create_backup(base_dir: Path, entries: List[FileEntry]) -> Optional[Path]:
    """
    Create a timestamped zip in <base_dir>/backups/ containing all
    existing application files that are about to be overwritten.

    Returns the backup path, or None if nothing to back up or on error.
    """
    to_backup = [e for e in entries if not e.is_new and not e.is_protected]
    if not to_backup:
        return None

    backups_dir = base_dir / "backups"
    try:
        backups_dir.mkdir(exist_ok=True)
    except OSError as exc:
        logger.warning("Could not create backups dir: %s", exc)
        return None

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backups_dir / f"update_backup_{ts}.zip"

    try:
        with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for entry in to_backup:
                full = base_dir / entry.dest_path
                if full.exists():
                    zf.write(full, entry.dest_path)
        logger.info("Backup created at %s", backup_path)
        return backup_path
    except Exception as exc:
        logger.warning("Backup creation failed: %s", exc)
        try:
            backup_path.unlink(missing_ok=True)
        except Exception:
            pass
        return None


# ---------------------------------------------------------------------------
# Install
# ---------------------------------------------------------------------------

def install_update(
    zip_path: Path,
    base_dir: Path,
    entries: List[FileEntry],
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> InstallResult:
    """
    Copy installable files from *zip_path* into *base_dir*.

    *progress_callback(current, total, filename)* is called before each file
    so the UI can update a progress bar.  Progress is reported only when the
    integer percentage changes (≤ 100 callbacks total) to keep the UI snappy.

    Protected files are silently skipped and reported in result.skipped_protected.
    Files are extracted directly via ZipFile.extract(); locked executables (e.g.
    the running Settings Manager) are saved as .pending and applied on restart.
    """
    result = InstallResult()

    installable = [e for e in entries if not e.is_protected]
    total = len(installable)

    if total == 0:
        result.success = True
        result.skipped_protected = [e.dest_path for e in entries if e.is_protected]
        return result

    # Create backup before touching anything.
    backup = create_backup(base_dir, entries)
    result.backup_path = str(backup) if backup else None

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            last_pct = -1
            for idx, entry in enumerate(installable, 1):
                if progress_callback:
                    pct = int(idx / total * 100)
                    if pct != last_pct:
                        progress_callback(idx, total, entry.dest_path)
                        last_pct = pct

                dest = base_dir / entry.dest_path
                try:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        zf.extract(entry.zip_path, base_dir)
                        result.installed.append(entry.dest_path)
                    except PermissionError:
                        # File is locked by a running process — write as .pending.
                        # A restart script will move it into place after the app closes.
                        pending = dest.with_suffix(dest.suffix + ".pending")
                        pending.write_bytes(zf.read(entry.zip_path))
                        result.pending_restart.append(entry.dest_path)
                        logger.info("Deferred (locked): %s → %s", entry.dest_path, pending.name)
                except Exception as exc:
                    result.failed.append((entry.dest_path, str(exc)))
                    logger.warning("Failed to install %s: %s", entry.dest_path, exc)

    except Exception as exc:
        result.error = str(exc)
        logger.error("Install aborted: %s", exc)
        return result

    result.skipped_protected = [e.dest_path for e in entries if e.is_protected]
    result.success = len(result.failed) == 0

    if result.pending_restart:
        try:
            sentinel = base_dir / RESTART_PENDING_FILENAME
            sentinel.write_text(
                json.dumps(result.pending_restart, indent=2), encoding="utf-8"
            )
        except Exception as exc:
            logger.warning("Could not write restart sentinel: %s", exc)

    return result


# ---------------------------------------------------------------------------
# Restore
# ---------------------------------------------------------------------------

def restore_backup(
    backup_zip: Path,
    base_dir: Path,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> InstallResult:
    """
    Restore files from a backup zip, undoing a previous update.

    Same PermissionError → .pending deferral as install_update so a locked
    running exe (e.g. the Settings Manager itself) is handled gracefully.
    """
    result = InstallResult()

    try:
        with zipfile.ZipFile(backup_zip, "r") as zf:
            names = [
                n for n in zf.namelist()
                if not n.endswith("/") and not n.endswith("\\")
            ]
            total = len(names)
            if total == 0:
                result.success = True
                return result

            last_pct = -1
            for idx, name in enumerate(names, 1):
                if progress_callback:
                    pct = int(idx / total * 100)
                    if pct != last_pct:
                        progress_callback(idx, total, name)
                        last_pct = pct

                dest = base_dir / name.replace("/", os.sep)
                try:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        zf.extract(name, base_dir)
                        result.installed.append(name)
                    except PermissionError:
                        pending = dest.with_suffix(dest.suffix + ".pending")
                        pending.write_bytes(zf.read(name))
                        result.pending_restart.append(name)
                        logger.info("Deferred restore (locked): %s", name)
                except Exception as exc:
                    result.failed.append((name, str(exc)))
                    logger.warning("Failed to restore %s: %s", name, exc)

    except zipfile.BadZipFile:
        result.error = "Not a valid zip file."
        return result
    except Exception as exc:
        result.error = str(exc)
        return result

    result.success = len(result.failed) == 0

    if result.pending_restart:
        try:
            sentinel = base_dir / RESTART_PENDING_FILENAME
            sentinel.write_text(
                json.dumps(result.pending_restart, indent=2), encoding="utf-8"
            )
        except Exception as exc:
            logger.warning("Could not write restart sentinel: %s", exc)

    return result


# ---------------------------------------------------------------------------
# Install log
# ---------------------------------------------------------------------------

def write_install_log(
    base_dir: Path,
    zip_path: Path,
    manifest: UpdateManifest,
    result: InstallResult,
) -> Path:
    """
    Prepend a human-readable log entry to <base_dir>/update_log.txt.

    Keeps the full history so the user can review previous installs.
    Returns the log path.
    """
    log_path = base_dir / "update_log.txt"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "IL-2 Campaign Tracker – Update Log",
        "===================================",
        f"Date/Time : {ts}",
        f"Package   : {zip_path.name}",
        f"Version   : {manifest.version or 'unknown'}",
        f"Result    : {'SUCCESS' if result.success else 'FAILED'}",
        "",
        f"Installed ({len(result.installed)} files):",
    ]
    for f in result.installed:
        lines.append(f"  + {f}")

    if result.skipped_protected:
        lines.append("")
        lines.append(f"Skipped – protected user files ({len(result.skipped_protected)}):")
        for f in result.skipped_protected:
            lines.append(f"  ~ {f}")

    if result.pending_restart:
        lines.append("")
        lines.append(f"Pending restart ({len(result.pending_restart)} files — applied on next launch):")
        for f in result.pending_restart:
            lines.append(f"  > {f}")

    if result.failed:
        lines.append("")
        lines.append(f"Failed ({len(result.failed)} files):")
        for f, err in result.failed:
            lines.append(f"  ! {f}: {err}")

    if result.backup_path:
        lines.append("")
        lines.append(f"Backup   : {result.backup_path}")

    if result.error:
        lines.append("")
        lines.append(f"Fatal error: {result.error}")

    new_entry = "\n".join(lines)

    try:
        existing = ""
        if log_path.exists():
            try:
                existing = log_path.read_text(encoding="utf-8")
            except Exception:
                pass
        separator = "\n\n" + "─" * 60 + "\n\n" if existing else ""
        log_path.write_text(new_entry + separator + existing, encoding="utf-8")
    except Exception as exc:
        logger.warning("Could not write install log: %s", exc)

    return log_path
