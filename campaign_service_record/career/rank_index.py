"""
RankIndex: maps (country_subfolder, rank_name_string) to CampaignRanksAwards image files.

Like AwardIndex, it scans JSON sidecar files alongside each asset, but indexes ALL
sidecar entries without filtering on id format.  Award sidecars carry numeric ids
("201002"); rank sidecars carry English name strings ("Leutnant").  Both coexist in
the index — callers supply the exact id string they expect.

Sidecar format:
    {"id": "Leutnant", "id_type": "normal"}

id_type values:
    normal  – image for detail page / event list
    big     – larger image for modal / popup

Usage:
    index = RankIndex.build(assets_root)
    asset = index.get("Germany", "Leutnant", "normal")       # -> AwardAsset or None
    asset = index.get_with_normal_fallback("Germany", "Leutnant", "big")  # big or normal
    if asset:
        url = f"/api/career_assets/CampaignRanksAwards/{asset.subfolder}/{asset.filename}"
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple

from campaign_service_record.career.award_index import AwardAsset

logger = logging.getLogger(__name__)

# Country subfolders to scan — same list as AwardIndex
_COUNTRY_SUBFOLDERS = ['Germany', 'Britain', 'US', 'USSR/early', 'USSR/late']

# Internal index type alias
_Index = Dict[Tuple[str, str], Dict[str, AwardAsset]]


class RankIndex:
    """
    Sidecar index keyed by (subfolder, id_string).

    Indexes ALL sidecar entries regardless of id format — both numeric award ids
    ("201002") and rank name strings ("Leutnant") are stored.  Callers are
    responsible for supplying the correct id string.

    Build once at application startup via RankIndex.build(assets_root).
    """

    def __init__(self, index: _Index):
        self._index = index

    # ------------------------------------------------------------------
    # Class methods
    # ------------------------------------------------------------------

    @classmethod
    def build(cls, assets_root: Path) -> "RankIndex":
        """
        Scan JSON sidecar files under assets_root/CampaignRanksAwards/<country>/
        and return a populated RankIndex.

        Every sidecar entry is indexed — there is no filter on id format.
        """
        cra_root = assets_root / 'CampaignRanksAwards'
        index: _Index = {}

        for subfolder in _COUNTRY_SUBFOLDERS:
            country_dir = cra_root / subfolder
            if not country_dir.is_dir():
                logger.debug("RankIndex: country dir not found: %s", country_dir)
                continue

            for json_path in sorted(country_dir.glob('*.json')):
                try:
                    data = json.loads(json_path.read_text(encoding='utf-8'))
                    id_str  = str(data.get('id',      '')).strip()
                    id_type = str(data.get('id_type', '')).strip()

                    if not id_str or not id_type:
                        continue

                    # json_path.stem strips ".json" → asset filename
                    # e.g. "leutnant.png.json" → "leutnant.png"
                    filename = json_path.stem

                    key = (subfolder, id_str)
                    index.setdefault(key, {})[id_type] = AwardAsset(
                        subfolder=subfolder,
                        filename=filename,
                    )
                except Exception as exc:
                    logger.debug(
                        "RankIndex: failed to parse sidecar %s: %s", json_path, exc
                    )

        logger.info(
            "RankIndex: indexed %d (subfolder, id) pairs from %s",
            len(index), cra_root,
        )
        return cls(index)

    @classmethod
    def empty(cls) -> "RankIndex":
        """Return an empty index used when assets_root is unavailable."""
        return cls({})

    # ------------------------------------------------------------------
    # Instance methods
    # ------------------------------------------------------------------

    def get(self, subfolder: str, id_str: str, id_type: str) -> Optional[AwardAsset]:
        """Return AwardAsset for (subfolder, id_str, id_type), or None."""
        return self._index.get((subfolder, id_str), {}).get(id_type)

    def get_with_normal_fallback(
        self, subfolder: str, id_str: str, id_type: str
    ) -> Optional[AwardAsset]:
        """
        Return the requested id_type asset; fall back to 'normal' if not found.

        Useful for modal images: returns big if present, otherwise normal.
        """
        entry = self._index.get((subfolder, id_str), {})
        return entry.get(id_type) or entry.get('normal')

    def __len__(self) -> int:
        return len(self._index)

    def __bool__(self) -> bool:
        return bool(self._index)
