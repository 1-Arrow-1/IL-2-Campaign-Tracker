"""
Helpers for importing stock IL-2 campaigns from Campaigns.gtp.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class StockCampaignImportResult:
    game_directory: str
    extractor_path: str
    archive_path: str
    extraction_root: str
    source_campaigns_dir: str
    destination_campaigns_dir: str
    imported_campaigns: List[str]
    skipped_campaigns: List[str]
    extractor_exit_code: int = 0
    extractor_stdout: str = ""
    extractor_stderr: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)


def get_bundled_resource_path(relative_path: str) -> Path:
    """
    Resolve a bundled resource in dev and PyInstaller one-file mode.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative_path
    return Path(__file__).resolve().parent.parent / relative_path


def get_default_extractor_path() -> Path:
    """
    Return the bundled unGTP extractor path.
    """
    return get_bundled_resource_path("unGTP-IL2.exe")


def validate_game_directory(game_dir: Path) -> Path:
    """
    Validate the selected IL-2 game directory and return data/Campaigns.gtp.
    """
    game_dir = Path(game_dir).expanduser().resolve()
    archive_path = game_dir / "data" / "Campaigns.gtp"
    if not game_dir.exists():
        raise FileNotFoundError(f"Game directory not found: {game_dir}")
    if not archive_path.is_file():
        raise FileNotFoundError(f"Campaigns.gtp not found: {archive_path}")
    return archive_path


def find_extracted_campaigns_dir(extraction_root: Path) -> Optional[Path]:
    """
    Locate the extracted Campaigns directory created by unGTP.
    """
    candidates = [
        extraction_root / "swf" / "Campaigns",
        extraction_root / "swf" / "campaigns",
        extraction_root / "Campaigns",
        extraction_root / "campaigns",
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return None


def list_campaign_subfolders(campaigns_dir: Path) -> List[str]:
    """
    Return sorted campaign folder names for a Campaigns directory.
    """
    campaigns_dir = Path(campaigns_dir)
    if not campaigns_dir.is_dir():
        return []
    return sorted(
        entry.name
        for entry in campaigns_dir.iterdir()
        if entry.is_dir()
    )


def copy_campaign_subfolders(source_campaigns_dir: Path, destination_campaigns_dir: Path) -> tuple[List[str], List[str]]:
    """
    Copy individual campaign subfolders, skipping only existing campaign folders.
    """
    source_campaigns_dir = Path(source_campaigns_dir)
    destination_campaigns_dir = Path(destination_campaigns_dir)
    destination_campaigns_dir.mkdir(parents=True, exist_ok=True)

    imported: List[str] = []
    skipped: List[str] = []

    for entry in sorted(source_campaigns_dir.iterdir(), key=lambda path: path.name.lower()):
        if not entry.is_dir():
            continue
        target = destination_campaigns_dir / entry.name
        if target.exists():
            skipped.append(entry.name)
            continue
        shutil.copytree(entry, target)
        imported.append(entry.name)

    return imported, skipped


def summarize_direct_import(
    existing_campaigns: List[str],
    resulting_campaigns: List[str],
) -> Tuple[List[str], List[str]]:
    """
    Summarize extraction results when unGTP writes directly into data/Campaigns.
    """
    existing_set = set(existing_campaigns)
    resulting_set = set(resulting_campaigns)
    imported = sorted(resulting_set - existing_set, key=str.lower)
    skipped = sorted(resulting_set & existing_set, key=str.lower)
    return imported, skipped


def import_stock_campaigns(
    game_directory: Path,
    extractor_path: Optional[Path] = None,
    timeout_seconds: int = 300,
) -> StockCampaignImportResult:
    """
    Extract stock campaigns from Campaigns.gtp and copy missing campaign folders.
    """
    game_directory = Path(game_directory).expanduser().resolve()
    archive_path = validate_game_directory(game_directory)
    extractor = Path(extractor_path or get_default_extractor_path()).expanduser().resolve()
    if not extractor.is_file():
        raise FileNotFoundError(f"unGTP-IL2.exe not found: {extractor}")

    data_dir = game_directory / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    destination_campaigns_dir = data_dir / "Campaigns"
    existing_campaigns = list_campaign_subfolders(destination_campaigns_dir)

    extraction_root = data_dir / "(null)"
    extractor_to_run = extractor
    cleanup_extractor_copy = False

    # unGTP behaves like the manual drag/drop workflow when executed from IL-2\data.
    if extractor.parent != data_dir:
        with tempfile.NamedTemporaryFile(
            dir=data_dir,
            prefix="__il2ct_ungtp_",
            suffix=extractor.suffix,
            delete=False,
        ) as temp_extractor:
            extractor_to_run = Path(temp_extractor.name)
        shutil.copy2(extractor, extractor_to_run)
        cleanup_extractor_copy = True

    try:
        result = subprocess.run(
            [str(extractor_to_run), str(archive_path)],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            cwd=str(data_dir),
        )
    finally:
        if cleanup_extractor_copy:
            try:
                extractor_to_run.unlink()
            except OSError:
                pass

    source_campaigns_dir = find_extracted_campaigns_dir(extraction_root)
    if source_campaigns_dir is None and destination_campaigns_dir.is_dir():
        source_campaigns_dir = destination_campaigns_dir

    if source_campaigns_dir is None:
        raise RuntimeError(
            "Stock campaign extraction did not produce a Campaigns directory."
        )

    if source_campaigns_dir.resolve() == destination_campaigns_dir.resolve():
        imported, skipped = summarize_direct_import(
            existing_campaigns=existing_campaigns,
            resulting_campaigns=list_campaign_subfolders(destination_campaigns_dir),
        )
    else:
        imported, skipped = copy_campaign_subfolders(
            source_campaigns_dir=source_campaigns_dir,
            destination_campaigns_dir=destination_campaigns_dir,
        )

    return StockCampaignImportResult(
        game_directory=str(game_directory),
        extractor_path=str(extractor),
        archive_path=str(archive_path),
        extraction_root=str(extraction_root),
        source_campaigns_dir=str(source_campaigns_dir),
        destination_campaigns_dir=str(destination_campaigns_dir),
        imported_campaigns=imported,
        skipped_campaigns=skipped,
        extractor_exit_code=result.returncode,
        extractor_stdout=result.stdout or "",
        extractor_stderr=result.stderr or "",
    )


def write_result_json(result: StockCampaignImportResult, destination: Path) -> None:
    """
    Serialize an import result for the elevated helper path.
    """
    destination = Path(destination)
    destination.write_text(
        json.dumps(result.to_dict(), indent=2),
        encoding="utf-8",
    )
