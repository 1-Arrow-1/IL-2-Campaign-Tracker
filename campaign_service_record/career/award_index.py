"""
AwardIndex: maps career event award IDs (event.tpar2) to CampaignRanksAwards image files.

Scans JSON sidecar files (e.g. iron_cross_1st.dds.json) alongside each asset.

Sidecar format:
    {"id": "201002", "id_type": "normal"}

id_type values:
    normal  – small image for timeline / event list display
    big     – medium image for modal / popup
    big1    – large image for the medal showcase canvas

Usage:
    index = AwardIndex.build(assets_root)
    # assets_root is the directory that contains a 'CampaignRanksAwards' subfolder.

    asset = index.get('201002', 'normal')   # -> AwardAsset or None
    if asset:
        url = f'/api/career_assets/CampaignRanksAwards/{asset.subfolder}/{asset.filename}'
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Subfolders to scan, relative to <assets_root>/CampaignRanksAwards/
_COUNTRY_SUBFOLDERS = ['Germany', 'Britain', 'US', 'USSR/early', 'USSR/late']


@dataclass(frozen=True)
class AwardAsset:
    subfolder: str   # e.g. "Germany" or "USSR/early"
    filename: str    # e.g. "iron_cross_1st.dds"

    @property
    def name_key(self) -> str:
        """
        i18n name key derived from filename stem, with size suffixes stripped.

        Examples:
            "iron_cross_1st.dds"      -> "iron_cross_1st"
            "iron_cross_1st_big.dds"  -> "iron_cross_1st"
            "iron_cross_1st_big1.png" -> "iron_cross_1st"
        """
        stem = Path(self.filename).stem   # strip last extension, e.g. ".dds"
        for suffix in ('_big1', '_big'):
            if stem.endswith(suffix):
                return stem[: -len(suffix)]
        return stem


class AwardIndex:
    """
    Lookup table: award_id -> {id_type -> AwardAsset}

    Build once at application startup via AwardIndex.build(assets_root).
    assets_root should be the directory that contains a 'CampaignRanksAwards'
    subfolder with country subfolders and *.json sidecar files.
    """

    def __init__(self, index: Dict[str, Dict[str, AwardAsset]]):
        self._index = index

    # ------------------------------------------------------------------
    # Class methods
    # ------------------------------------------------------------------

    @classmethod
    def build(cls, assets_root: Path) -> "AwardIndex":
        """
        Scan JSON sidecar files under assets_root/CampaignRanksAwards/<country>/
        and return a populated AwardIndex.

        Non-numeric IDs (e.g. canvas/overlay JSON files) are silently skipped.
        """
        cra_root = assets_root / 'CampaignRanksAwards'
        index: Dict[str, Dict[str, AwardAsset]] = {}

        for subfolder in _COUNTRY_SUBFOLDERS:
            country_dir = cra_root / subfolder
            if not country_dir.is_dir():
                logger.debug("AwardIndex: country dir not found: %s", country_dir)
                continue

            for json_path in sorted(country_dir.glob('*.json')):
                try:
                    data = json.loads(json_path.read_text(encoding='utf-8'))
                    award_id = str(data.get('id', '')).strip()
                    id_type = str(data.get('id_type', '')).strip()

                    # Only index numeric award IDs; skip canvas/overlay/etc.
                    if not award_id or not id_type or not award_id[:1].isdigit():
                        continue

                    # json_path.stem strips ".json", leaving the asset filename,
                    # e.g. "iron_cross_1st.dds.json" -> stem = "iron_cross_1st.dds"
                    filename = json_path.stem

                    index.setdefault(award_id, {})[id_type] = AwardAsset(
                        subfolder=subfolder,
                        filename=filename,
                    )
                except Exception as exc:
                    logger.debug(
                        "AwardIndex: failed to parse sidecar %s: %s", json_path, exc
                    )

        logger.info(
            "AwardIndex: indexed %d awards from %s", len(index), cra_root
        )
        return cls(index)

    @classmethod
    def empty(cls) -> "AwardIndex":
        """Return an empty index (used when assets_root is unavailable)."""
        return cls({})

    # ------------------------------------------------------------------
    # Instance methods
    # ------------------------------------------------------------------

    def get(self, award_id: str, id_type: str) -> Optional[AwardAsset]:
        """Return AwardAsset for award_id + id_type, or None if not found."""
        return self._index.get(str(award_id), {}).get(id_type)

    def __len__(self) -> int:
        return len(self._index)

    def __bool__(self) -> bool:
        return bool(self._index)
