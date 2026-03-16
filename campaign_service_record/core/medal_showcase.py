"""
Medal Showcase - Excel coordinate parsing and showcase data builder.

Parses IL-2_Tracker_award_coordinates.xlsx to build per-country medal
placement data for the Medal Showcase modal.

Excel format (Sheet1):
  - Section header rows in column A:  "USSR (early)", "USSR (late)", "USA",
    "Germany", "Britain"
  - Within each section:
      Col A: medal name (no extension, e.g. "iron_cross_2nd_big1") or
             overlay identifier (e.g. "Germany_overlay")
      Col B: x  (top-left, pixels)
      Col C: y  (top-left, pixels)
      Col D: width
      Col E: height
      Col F: unused
      Col G-K: replacement names (higher-tier variants, left=base+1 …
               right=highest)

Country keys used throughout:
  "ussr_early", "ussr_late", "usa", "germany", "britain"

Asset folder mapping (relative to CampaignRanksAwards/):
  ussr_early  -> USSR/early
  ussr_late   -> USSR/late
  usa         -> US
  germany     -> Germany
  britain     -> Britain

Developer notes
---------------
* Excel is the single source of truth for coordinates.  Never hard-code
  positions in Python or JavaScript.
* Overlay rows are identified by the word "overlay" in their name
  (case-insensitive) or the special marker "glass_overlay_ussr".
* Replacement selection: for each slot (column A), collect the chain
  [col_A] + [col_G … col_K].  Walk from highest (rightmost) to lowest
  (col_A).  Show the first entry in that chain that the player has earned.
* USSR early/late decision: compare the campaign's last mission date against
  USSR_REDESIGN_DATE.  Awards earned before that date use early assets;
  awards earned on/after use late assets.  For the showcase we use whichever
  canvas matches the campaign's current era.
* The "no re-earning" rule (USSR) is enforced by max_awards:1 in the award
  config, so no extra logic is needed here.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Import the canonical redesign date from path_utils (same constant used by
# resolve_country_folder for step3 asset selection).
try:
    from campaign_service_record.utils.path_utils import USSR_TRANSITION_DATE as USSR_REDESIGN_DATE
except ImportError:
    USSR_REDESIGN_DATE = date(1943, 1, 6)  # fallback

# Section header in Excel  ->  internal country key
SECTION_HEADERS: dict[str, str] = {
    'USSR (early)': 'ussr_early',
    'USSR (late)': 'ussr_late',
    'USA': 'usa',
    'Germany': 'germany',
    'Britain': 'britain',
}

# internal country key  ->  relative folder under CampaignRanksAwards/
ASSET_FOLDER: dict[str, str] = {
    'ussr_early':  'USSR/early',
    'ussr_late':   'USSR/late',
    'usa':         'US',
    'germany':     'Germany',
    'germany_ext': 'Germany',
    'britain':     'Britain',
}

# country key  ->  canvas filename (just the filename, not full path)
CANVAS_FILENAME: dict[str, str] = {
    'ussr_early': 'USSR_canvas.png',
    'ussr_late':  'USSR_canvas.png',
    'usa':        'usa_canvas.png',
    'germany':    'Germany_canvas.png',
    'britain':    'Britain_canvas.png',
}

# country key  ->  overlay filename
OVERLAY_FILENAME: dict[str, str] = {
    'ussr_early': 'USSR_overlay.png',
    'ussr_late':  'USSR_overlay.png',
    'usa':        'usa_overlay.png',
    'germany':    'Germany_overlay.png',
    'britain':    'Britain_overlay.png',
}

# Career-specific canvas filenames (use _career suffix)
CAREER_CANVAS_FILENAME: dict[str, str] = {
    'ussr_early':  'USSR_canvas_career.png',
    'ussr_late':   'USSR_canvas_career.png',
    'usa':         'usa_canvas_career.png',
    'germany':     'Germany_canvas_career.png',
    'germany_ext': 'Germany_canvas_career_ext.png',
    'britain':     'Britain_canvas_career.png',
}

# Career-specific overlay filenames (USSR has _career suffix; others shared with campaign)
CAREER_OVERLAY_FILENAME: dict[str, str] = {
    'ussr_early':  'USSR_overlay_career.png',
    'ussr_late':   'USSR_overlay_career.png',
    'usa':         'usa_overlay.png',
    'germany':     'Germany_overlay.png',
    'germany_ext': 'Germany_overlay_ext.png',
    'britain':     'Britain_overlay.png',
}

# Normalise "Soviet Union" / "USSR" from campaign data to internal key
_CAMPAIGN_COUNTRY_MAP: dict[str, str] = {
    'germany':             'germany',
    'britain':             'britain',
    'uk':                  'britain',
    'great britain':       'britain',
    'united kingdom':      'britain',
    'usa':                 'usa',
    'us':                  'usa',
    'united states':       'usa',
    'united states of america': 'usa',
    'soviet union':        'ussr',
    'ussr':                'ussr',
    'russia':              'ussr',
}


# Achievement folder IDs that indicate the extended German medals are installed.
_GERMAN_EXT_ACHIEVEMENT_IDS = ('201037', '201038')


def has_german_ext_medals(game_dir: Path) -> bool:
    """
    Return True if either of the extended German medal achievement folders
    (201037 / 201038) exists under <game_dir>/data/swf/il2/achievements/.

    These folders are created by the IL-2 mod that adds grand_cross and
    star_grand_cross.  When present, the career showcase should use the
    wider germany_ext canvas and overlay.
    """
    base = game_dir / 'data' / 'swf' / 'il2' / 'achievements'
    for aid in _GERMAN_EXT_ACHIEVEMENT_IDS:
        if (base / aid).exists():
            logger.debug(
                "[medal_showcase] German ext medals detected (found %s)",
                base / aid,
            )
            return True
    return False


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class MedalEntry:
    """One medal slot from the Excel, with optional replacement chain."""
    __slots__ = ('name', 'x', 'y', 'w', 'h', 'replacements',
                 'img_w', 'img_h', 'img_x', 'img_y')

    def __init__(
        self,
        name: str,
        x: int, y: int, w: int, h: int,
        replacements: list[str],
        img_w: int = 0, img_h: int = 0,
        img_x: int = 0, img_y: int = 0,
    ) -> None:
        self.name         = name
        self.x            = x
        self.y            = y
        self.w            = w
        self.h            = h
        self.replacements = replacements  # ordered from base+1 to highest
        # Image natural dimensions and content offset within the PNG
        # (the transparent padding region before the actual medal pixels)
        self.img_w        = img_w
        self.img_h        = img_h
        self.img_x        = img_x
        self.img_y        = img_y

    def full_chain(self) -> list[str]:
        """Return [base, *replacements] – all candidates, lowest first."""
        return [self.name] + self.replacements

    def to_dict(self) -> dict:
        d = {
            'name':         self.name,
            'x':            self.x,
            'y':            self.y,
            'w':            self.w,
            'h':            self.h,
            'replacements': self.replacements,
        }
        if self.img_w:
            d['img_w'] = self.img_w
            d['img_h'] = self.img_h
            d['img_x'] = self.img_x
            d['img_y'] = self.img_y
        return d


class CountryShowcase:
    """All placement data for one country key."""
    __slots__ = ('medals', 'overlay')

    def __init__(
        self,
        medals: list[MedalEntry],
        overlay: Optional[MedalEntry],
    ) -> None:
        self.medals  = medals
        self.overlay = overlay


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------

def parse_json_coordinates(json_path: Path) -> dict[str, CountryShowcase]:
    """
    Parse the award-coordinates JSON file into a per-country dict.

    The JSON is produced by the one-time conversion script from the Excel
    source file (IL-2_Tracker_award_coordinates.xlsx).  Keeping the JSON
    in the repo removes the openpyxl / numpy runtime dependency.

    Returns:
        { country_key: CountryShowcase }

    Raises:
        FileNotFoundError  if the file does not exist
        ValueError         on malformed JSON structure
    """
    import json  # stdlib, always available

    if not json_path.exists():
        raise FileNotFoundError(f"Coordinate file not found: {json_path}")

    raw = json.loads(json_path.read_text(encoding='utf-8'))

    result: dict[str, CountryShowcase] = {}
    for country_key, section in raw.items():
        medals = [
            MedalEntry(
                name=m['name'],
                x=m['x'], y=m['y'], w=m['w'], h=m['h'],
                replacements=m.get('replacements', []),
                img_w=m.get('img_w', 0), img_h=m.get('img_h', 0),
                img_x=m.get('img_x', 0), img_y=m.get('img_y', 0),
            )
            for m in section.get('medals', [])
        ]
        ovl_raw = section.get('overlay')
        overlay = (
            MedalEntry(
                name=ovl_raw['name'],
                x=ovl_raw['x'], y=ovl_raw['y'],
                w=ovl_raw['w'], h=ovl_raw['h'],
                replacements=ovl_raw.get('replacements', []),
            )
            if ovl_raw else None
        )
        result[country_key] = CountryShowcase(medals=medals, overlay=overlay)

    logger.info(
        "[medal_showcase] Loaded %d country sections from %s",
        len(result), json_path.name,
    )
    return result


# ---------------------------------------------------------------------------
# Cached loader
# ---------------------------------------------------------------------------

_cached_coordinates: Optional[dict[str, CountryShowcase]] = None
_cached_excel_mtime: Optional[float] = None


def load_coordinates(json_path: Path) -> dict[str, CountryShowcase]:
    """
    Return parsed coordinates, re-parsing if the JSON file has changed.
    Thread-safe via GIL (single writer, dict swap).
    """
    global _cached_coordinates, _cached_excel_mtime

    try:
        mtime = json_path.stat().st_mtime
    except OSError:
        mtime = None

    if _cached_coordinates is None or mtime != _cached_excel_mtime:
        _cached_coordinates = parse_json_coordinates(json_path)
        _cached_excel_mtime = mtime

    return _cached_coordinates


_cached_career_coordinates: Optional[dict[str, CountryShowcase]] = None
_cached_career_mtime: Optional[float] = None


def load_career_coordinates(json_path: Path) -> dict[str, CountryShowcase]:
    """
    Return parsed career coordinates, re-parsing if the JSON file has changed.
    Uses a separate cache from load_coordinates() (campaign cache).
    Thread-safe via GIL (single writer, dict swap).
    """
    global _cached_career_coordinates, _cached_career_mtime

    try:
        mtime = json_path.stat().st_mtime
    except OSError:
        mtime = None

    if _cached_career_coordinates is None or mtime != _cached_career_mtime:
        _cached_career_coordinates = parse_json_coordinates(json_path)
        _cached_career_mtime = mtime

    return _cached_career_coordinates


# ---------------------------------------------------------------------------
# Country resolution helpers
# ---------------------------------------------------------------------------

def resolve_showcase_country(campaign_country: str) -> str:
    """
    Map a campaign's country string to an internal country key.

    For USSR, returns "ussr" (caller must decide early/late based on date).
    """
    return _CAMPAIGN_COUNTRY_MAP.get((campaign_country or '').strip().lower(), '')


def resolve_ussr_variant(last_mission_date: Optional[str]) -> str:
    """
    Decide "ussr_early" or "ussr_late" based on the campaign's last mission.
    Falls back to "ussr_early" if date cannot be parsed.
    """
    if not last_mission_date:
        return 'ussr_early'
    for fmt in ('%Y-%m-%d', '%d.%m.%Y'):
        try:
            d = datetime.strptime(last_mission_date, fmt).date()
            return 'ussr_late' if d >= USSR_REDESIGN_DATE else 'ussr_early'
        except ValueError:
            continue
    return 'ussr_early'


# ---------------------------------------------------------------------------
# Award-name  <->  showcase-name mapping
# ---------------------------------------------------------------------------

def award_image_to_showcase_name(image_field: str) -> str:
    """
    Derive the showcase identifier (without extension) from the award's
    image field stored in campaign_events.json.

    Examples:
        "iron_cross_2nd.dds"               -> "iron_cross_2nd_big1"
        "CampaignRanksAwards/Germany/dfc.dds" -> "dfc_big1"
        "dfc_bar.dds"                      -> "dfc_bar_big1"
        "air_medal_big.dds"                -> "air_medal_big1"
    """
    if not image_field:
        return ''
    stem = Path(image_field).stem          # strip path + extension
    if stem.endswith('_big'):
        return stem + '1'
    return stem + '_big1'


def _split_award_size_suffix(name: str) -> tuple[str, str]:
    """Return (base_name, size_suffix) where suffix is '', '_big', or '_big1'."""
    n = (name or '').strip()
    if n.endswith('_big1'):
        return n[:-5], '_big1'
    if n.endswith('_big'):
        return n[:-4], '_big'
    return n, ''


def _award_name_candidates_for_context(
    base_name: str,
    context: str,
) -> list[str]:
    """
    Build deterministic filename stem candidates for the requested context.

    Career detail showcase prefers large medal variants:
      *_big1 -> *_big -> original.
    Other contexts preserve the incoming name.
    """
    stem_base, _ = _split_award_size_suffix(base_name)
    if not stem_base:
        return []

    if context == 'career_detail_showcase':
        return [f"{stem_base}_big1", f"{stem_base}_big", stem_base]

    return [base_name.strip()]


def _with_known_typo_variants(name: str) -> list[str]:
    """Return name plus known typo-normalized alternatives."""
    variants = [name]
    # Known typo in coordinate files: order_surov_* -> order_suvorov_*
    if 'surov' in name and 'suvorov' not in name:
        variants.append(name.replace('surov', 'suvorov'))
    return variants


def resolve_award_asset_path(
    base_name: str,
    country_key: str,
    assets_dir: Path,
    context: str = 'campaign_showcase',
) -> Optional[Path]:
    """
    Resolve the medal asset path for showcase rendering.

    For `career_detail_showcase`, variant preference is:
      *_big1 -> *_big -> original.
    For other contexts, the incoming name is used as-is.

    Returns:
        Path to existing PNG or DDS asset, or None if none found.
    """
    folder = ASSET_FOLDER.get(country_key, '')
    if not folder:
        return None
    name_candidates = _award_name_candidates_for_context(base_name, context)
    tried: list[str] = []

    for stem in name_candidates:
        for candidate in _with_known_typo_variants(stem):
            for ext in ('.png', '.dds'):
                path = assets_dir / folder / f"{candidate}{ext}"
                tried.append(path.name)
                if path.exists():
                    logger.debug(
                        "[medal_showcase] Resolved asset context=%s country=%s "
                        "base=%s -> %s",
                        context, country_key, base_name, path.name,
                    )
                    return path

    logger.warning(
        "[medal_showcase] Asset not found context=%s country=%s base=%s tried=%s",
        context, country_key, base_name, tried,
    )
    return None


@lru_cache(maxsize=512)
def _infer_asset_geometry(asset_path_str: str) -> tuple[int, int, int, int]:
    """
    Infer (img_w, img_h, img_x, img_y) from image alpha bounds.

    This is a runtime fallback for coordinate sets that do not include img_*
    metadata. Returns zeros when Pillow is unavailable or parsing fails.
    """
    try:
        from PIL import Image  # local import to avoid hard dependency at import time
    except Exception:
        return (0, 0, 0, 0)

    try:
        with Image.open(asset_path_str) as img:
            rgba = img.convert('RGBA')
            alpha = rgba.getchannel('A')
            bbox = alpha.getbbox()
            if bbox is None:
                return (rgba.width, rgba.height, 0, 0)
            return (rgba.width, rgba.height, int(bbox[0]), int(bbox[1]))
    except Exception:
        return (0, 0, 0, 0)


# ---------------------------------------------------------------------------
# Showcase builder
# ---------------------------------------------------------------------------

def build_showcase_data(
    country_key: str,
    earned_showcase_names: set[str],
    coordinates: dict[str, CountryShowcase],
    assets_dir: Path,
    tracker_asset_url_prefix: str = '/api/tracker_assets',
    canvas_filenames: Optional[dict] = None,
    overlay_filenames: Optional[dict] = None,
    asset_context: str = 'campaign_showcase',
) -> dict:
    """
    Build the JSON-serialisable showcase payload for the frontend.

    Args:
        country_key:            e.g. "ussr_late", "germany"
        earned_showcase_names:  set of showcase names the pilot has earned,
                                e.g. {"iron_cross_2nd_big1", "dfc_big1"}
        coordinates:            parsed Excel data
        assets_dir:             path to CampaignRanksAwards/ root directory
        tracker_asset_url_prefix: URL prefix for tracker assets

    Returns:
        {
            "country_key": "germany",
            "canvas_url":  "/api/tracker_assets/CampaignRanksAwards/Germany/Germany_canvas.png",
            "overlay": {
                "url": "...",
                "x": 32, "y": 0, "w": 2018, "h": 961
            },
            "medals": [
                { "image_url": "...", "x": 141, "y": 134, "w": 363, "h": 503, "name": "iron_cross_2nd_big1" },
                ...
            ]
        }
    """
    showcase = coordinates.get(country_key)
    if showcase is None:
        logger.warning(
            "[medal_showcase] No coordinate data for country key '%s'",
            country_key,
        )
        return {}

    _canvas_map  = canvas_filenames  or CANVAS_FILENAME
    _overlay_map = overlay_filenames or OVERLAY_FILENAME

    folder = ASSET_FOLDER.get(country_key, '')

    def _make_url(filename: str) -> str:
        return f"{tracker_asset_url_prefix}/CampaignRanksAwards/{folder}/{filename}"

    # Canvas URL
    canvas_file = _canvas_map.get(country_key, '')
    canvas_url  = _make_url(canvas_file) if canvas_file else ''

    # Overlay
    overlay_dict: Optional[dict] = None
    if showcase.overlay:
        ovl = showcase.overlay
        overlay_file = _overlay_map.get(country_key, '')
        if overlay_file:
            overlay_dict = {
                'url': _make_url(overlay_file),
                'x': ovl.x,
                'y': ovl.y,
                'w': ovl.w,
                'h': ovl.h,
            }

    # Medals – only earned slots
    placed_medals: list[dict] = []

    for entry in showcase.medals:
        chain = entry.full_chain()  # [base, rep1, rep2, …]  lowest to highest

        # Walk from HIGHEST to LOWEST to find the best earned variant
        chosen: Optional[str] = None
        for candidate in reversed(chain):
            # Normalise for comparison (strip trailing whitespace)
            c = candidate.strip()
            if c in earned_showcase_names:
                chosen = c
                break

        if chosen is None:
            continue  # player hasn't earned this award

        # Verify asset file exists
        asset_path = resolve_award_asset_path(
            chosen,
            country_key,
            assets_dir,
            context=asset_context,
        )
        if asset_path is None:
            # Try base entry as fallback
            if chosen != entry.name:
                asset_path = resolve_award_asset_path(
                    entry.name,
                    country_key,
                    assets_dir,
                    context=asset_context,
                )
            if asset_path is None:
                continue  # no usable image

        slot: dict = {
            'image_url': _make_url(asset_path.name),
            'x':         entry.x,
            'y':         entry.y,
            'w':         entry.w,
            'h':         entry.h,
            'name':      chosen,
        }
        if entry.img_w:
            slot['img_w'] = entry.img_w
            slot['img_h'] = entry.img_h
            slot['img_x'] = entry.img_x
            slot['img_y'] = entry.img_y
        elif asset_context == 'career_detail_showcase':
            img_w, img_h, img_x, img_y = _infer_asset_geometry(str(asset_path))
            if img_w and img_h:
                slot['img_w'] = img_w
                slot['img_h'] = img_h
                slot['img_x'] = img_x
                slot['img_y'] = img_y
        placed_medals.append(slot)

    return {
        'country_key': country_key,
        'canvas_url':  canvas_url,
        'overlay':     overlay_dict,
        'medals':      placed_medals,
    }


# ---------------------------------------------------------------------------
# Convenience: extract earned showcase names from campaign event list
# ---------------------------------------------------------------------------

def earned_showcase_names_from_events(
    events: list[dict],
) -> set[str]:
    """
    Extract the set of showcase image names (e.g. "dfc_big1") from
    campaign events.  Only award-type events contribute.

    USSR early/late note: both early and late images map to the same
    showcase name (the filename stem + _big1), so no era-specific logic
    is needed here.
    """
    result: set[str] = set()
    for ev in events:
        if ev.get('type') != 'award':
            continue
        image = ev.get('image', '')
        name  = award_image_to_showcase_name(image)
        if name:
            result.add(name)
    return result
