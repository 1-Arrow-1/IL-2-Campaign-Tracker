"""
Historical weather lookup via the Open-Meteo Archive API.
Free, no API key required, covers data from 1940-01-01 onwards.
https://open-meteo.com/en/docs/historical-weather-api

Location resolution priority for campaigns:
  1. Game-world (x, z) spawn position + map origin → real-world lat/lon (most precise)
  2. Read LANDSCAPE_* token from .msnbin file header → map centre coordinates
  3. Keyword match on campaign name / theatre infoId
  4. Open-Meteo geocoding fallback
"""
import json
import logging
import math
import re
from html import unescape
from pathlib import Path
from typing import Dict, Optional, Tuple
import urllib.error
import urllib.parse
import urllib.request

LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# IL-2 map keyword → (lat, lon, human place name)
# Used for both keyword matching on campaign/infoId names AND for matching
# extracted LANDSCAPE_* tokens from .msnbin files.
# Keys are lowercase; substring matching is used so "kuban" matches "LANDSCAPE_Kuban_a".
# ---------------------------------------------------------------------------
_IL2_LOCATIONS: Dict[str, Tuple[float, float, str]] = {
    # Eastern Front — South
    "kuban":         (45.35,  36.47, "Kuban / Kerch, Black Sea"),
    "kerch":         (45.35,  36.47, "Kerch, Crimea"),
    "taman":         (45.22,  36.72, "Taman Peninsula"),
    "novorossiysk":  (44.72,  37.77, "Novorossiysk"),
    "crimea":        (45.08,  34.08, "Crimea"),
    "sevastopol":    (44.61,  33.52, "Sevastopol"),
    "prokhorovka":   (51.02,  36.74, "Prokhorovka (Kursk)"),
    "stalin":        (48.70,  44.50, "Stalingrad"),
    "stalingrad":    (48.70,  44.50, "Stalingrad"),
    "volga":         (48.70,  44.50, "Stalingrad Front"),
    "kharkov":       (49.99,  36.23, "Kharkov"),
    "donbas":        (48.00,  37.80, "Donbas"),
    "odessa":        (46.48,  30.73, "Odessa"),
    "budapest":      (47.50,  19.04, "Budapest"),
    # Eastern Front — Centre / North
    "moscow":        (55.75,  37.62, "Moscow"),
    "moskva":        (55.75,  37.62, "Moscow"),
    "lapino":        (59.93,  30.32, "Leningrad Front"),
    "leningrad":     (59.93,  30.32, "Leningrad"),
    "novgorod":      (58.52,  31.27, "Novgorod"),
    "narva":         (59.38,  28.18, "Narva Front"),
    "vitebsk":       (55.19,  30.20, "Vitebsk"),
    "warsaw":        (52.23,  21.01, "Warsaw"),
    "berlin":        (52.52,  13.40, "Berlin"),
    # Western Front
    "rheinland":     (51.22,   6.78, "Rhineland"),
    "rhineland":     (51.22,   6.78, "Rhineland"),
    "rhein":         (51.22,   6.78, "Rhine Valley"),
    "westernfront":  (51.44,   5.48, "Western Front (Netherlands/Belgium)"),
    "bodenplatte":   (51.44,   5.48, "Bodenplatte"),
    "normandy":      (49.18,  -0.37, "Normandy"),
    "caen":          (49.18,  -0.37, "Caen"),
    "channel":       (50.50,   0.10, "English Channel coast"),
    "arras":         (50.29,   2.78, "Arras"),
    "somme":         (50.00,   2.50, "Somme"),
    "flanders":      (50.85,   2.88, "Flanders"),
    "ypres":         (50.85,   2.88, "Ypres"),
    "verdun":        (49.16,   5.39, "Verdun"),
    # Pacific / Other
    "newguinea":     (-9.44, 147.18, "New Guinea"),
    "new guinea":    (-9.44, 147.18, "New Guinea"),
    "papua":         (-9.44, 147.18, "Papua"),
    "rabaul":        (-4.20, 152.18, "Rabaul"),
    "solomon":       (-8.00, 159.00, "Solomon Islands"),
    # IL-2 career infoId keys (THEATRE_LABELS in chain_resolver.py)
    "bol41":         (59.93,  30.32, "Leningrad Front 1941"),
    "boo41":         (46.48,  30.73, "Odessa 1941"),
    "bom":           (55.75,  37.62, "Moscow Front"),
    "bos":           (48.70,  44.50, "Stalingrad Front"),
    "bok":           (45.35,  36.47, "Kuban / Kerch"),
    "boo44":         (46.48,  30.73, "Odessa 1944"),
    "bon":           (49.18,  -0.37, "Normandy"),
    "bobp":          (51.22,   6.78, "Rhineland / Bodenplatte"),
    "bop":           (51.02,  36.74, "Prokhorovka (Kursk)"),
}

# ---------------------------------------------------------------------------
# IL-2 map origins — real-world (lat, lon) at game-world (x=0, z=0).
# Allows converting player spawn coordinates to lat/lon for airfield-level weather.
#
# Coordinate system: x = metres East, z = metres North (flat-earth projection).
# Conversion:  lat = origin_lat + z / 111_320
#              lon = origin_lon + x / (111_320 * cos(lat_radians))
#
# Accuracy notes:
#   CONFIRMED  — derived from cross-referenced spawn position + known airfield coords
#   ESTIMATED  — derived from map geographic coverage; error ≤ ~30 km
# ---------------------------------------------------------------------------
_MAP_ORIGINS: Dict[str, Tuple[float, float]] = {
    # Eastern Front — South
    "kuban":         (44.495, 33.009),   # CONFIRMED  (Bagerovo 45.42N 36.53E ↔ x=275101 z=102964)
    "odessa":        (47.528, 24.490),   # ESTIMATED  (Bălți Moldova ↔ x=257449 z=25839)
    "prokhorovka":   (49.900, 34.150),   # ESTIMATED
    # Eastern Front — Centre / North
    "stalin":        (46.800, 41.100),   # ESTIMATED  (Stalingrad at NE quadrant)
    "moscow":        (54.100, 34.800),   # ESTIMATED  (Moscow at NE quadrant)
    "lapino":        (57.450, 27.300),   # ESTIMATED  (Leningrad at NE quadrant)
    "karelia":       (60.100, 27.300),   # ESTIMATED
    # Western Front
    "normandy":      (48.956, -3.867),   # ESTIMATED  (Manston 51.347N 1.343E ↔ x=362242 z=266205)
    "rheinland":     (49.700, 2.000),    # ESTIMATED  (map covers NL/Belgium/W Germany)
    "westernfront":  (49.700, 2.000),    # ESTIMATED  (same as Rheinland — Bodenplatte map)
    "arras":         (48.900, 0.500),    # ESTIMATED  (WWI Western Front)
    # IL-2 career infoId aliases (lowercase) — same origins as their landscape equivalents.
    # Allows game_coords_to_latlon() to work when called with infoId instead of landscape token.
    "bom":           (54.100, 34.800),   # Battle of Moscow
    "bos":           (46.800, 41.100),   # Battle of Stalingrad
    "bok":           (44.495, 33.009),   # Battle of Kuban
    "bol41":         (57.450, 27.300),   # Battle of Leningrad 1941
    "boo41":         (47.528, 24.490),   # Defence of Odessa
    "boo44":         (47.528, 24.490),   # Liberation of Odessa
    "bon":           (48.956, -3.867),   # Battle of Normandy
    "bobp":          (49.700, 2.000),    # Battle of Bodenplatte / Rheinland
    "bop":           (49.900, 34.150),   # Battle of Prokhorovka
}


def game_coords_to_latlon(
    x: float, z: float, landscape_suffix: str
) -> Optional[Tuple[float, float]]:
    """
    Convert IL-2 game-world (x, z) to real-world (lat, lon) using the map's
    known origin.  Returns None if the map origin is not in _MAP_ORIGINS.

    landscape_suffix: the part after LANDSCAPE_ in the msnbin header
    (e.g. 'Kuban_a', 'Stalin_s', 'westernfront_sp').
    """
    lower = landscape_suffix.lower()
    origin: Optional[Tuple[float, float]] = None
    # Longest-key substring match
    matched = [(k, v) for k, v in _MAP_ORIGINS.items() if k in lower]
    if matched:
        _, origin = max(matched, key=lambda m: len(m[0]))
    if origin is None:
        return None
    origin_lat, origin_lon = origin
    lat = origin_lat + z / 111_320.0
    lon = origin_lon + x / (111_320.0 * math.cos(math.radians(lat)))
    return round(lat, 5), round(lon, 5)


# WMO weather code → plain-English description
_WMO_CODES: Dict[int, str] = {
    0:  "clear sky",
    1:  "mainly clear",
    2:  "partly cloudy",
    3:  "overcast",
    45: "fog",
    48: "freezing fog",
    51: "light drizzle",
    53: "drizzle",
    55: "heavy drizzle",
    61: "light rain",
    63: "rain",
    65: "heavy rain",
    71: "light snow",
    73: "snow",
    75: "heavy snow",
    77: "snow grains",
    80: "light rain showers",
    81: "rain showers",
    82: "violent rain showers",
    85: "snow showers",
    86: "heavy snow showers",
    95: "thunderstorm",
    96: "thunderstorm with hail",
    99: "thunderstorm with heavy hail",
}

# In-process caches
_weather_cache: Dict[str, Optional[dict]] = {}          # "{lat:.4f},{lon:.4f}|{date}" → result
_campaign_coords_cache: Dict[str, Optional[Tuple[float, float, str]]] = {}  # campaign_name → coords
_eng_briefing_cache: Dict[str, Optional[str]] = {}

# ---------------------------------------------------------------------------
# Campaign .eng briefing weather
# ---------------------------------------------------------------------------

_ENG_WEATHER_RE = re.compile(
    r'Weather:\s*(?:</?[^>]+>\s*)*([^<\n\r]+)',
    re.IGNORECASE,
)
_ENG_MISSION_TYPE_RE = re.compile(
    r'Mission\s*type:\s*(?:</?[^>]+>\s*)*([^<\n\r]+)',
    re.IGNORECASE,
)
_ENG_ORDERS_RE = re.compile(r'Orders:\s*(.+?)(?:<br><br>|$)', re.IGNORECASE | re.DOTALL)
_ENG_FLIGHT_MISSION_RE = re.compile(r'Flight\s+Mission:\s*(.+?)(?:<br><br>|$)', re.IGNORECASE | re.DOTALL)
_ENG_MISSION_RE = re.compile(r'Mission:\s*(.+?)(?:<br><br>|$)', re.IGNORECASE | re.DOTALL)
_ENG_TIME_RE = re.compile(
    r'\bTime:\s*(?:</?[^>]+>\s*)*([0-2]?\d:[0-5]\d(?::[0-5]\d)?)\b',
    re.IGNORECASE,
)
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _normalize_briefing_value(value: str) -> str:
    text = unescape(str(value or ""))
    text = _HTML_TAG_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _resolve_eng_path(
    game_dir: str,
    campaign_name: str,
    mission_id: str,
    mission_file: str = "",
) -> Optional[Path]:
    if not game_dir:
        return None

    campaign_dir = Path(game_dir) / "data" / "Campaigns" / campaign_name
    if not campaign_dir.exists():
        return None

    candidates: list[Path] = []
    mission_file_name = str(mission_file or "").strip()
    if mission_file_name:
        candidates.append(campaign_dir / f"{Path(mission_file_name).stem}.eng")
    candidates.append(campaign_dir / f"{mission_id}.eng")

    for path in candidates:
        if path.exists():
            return path
    return None


def _read_eng_briefing_text(
    game_dir: str,
    campaign_name: str,
    mission_id: str,
    mission_file: str = "",
) -> Optional[str]:
    eng_path = _resolve_eng_path(game_dir, campaign_name, mission_id, mission_file=mission_file)
    if eng_path is None:
        return None

    cache_key = str(eng_path).lower()
    if cache_key in _eng_briefing_cache:
        return _eng_briefing_cache[cache_key]

    text: Optional[str] = None
    for enc in ("utf-16", "utf-8", "latin-1"):
        try:
            text = eng_path.read_text(encoding=enc)
            break
        except (UnicodeDecodeError, OSError):
            continue
    _eng_briefing_cache[cache_key] = text
    return text


def read_eng_story_context(
    game_dir: str,
    campaign_name: str,
    mission_id: str,
    mission_file: str = "",
) -> dict:
    """
    Extract lightweight story context from a mission .eng briefing.

    Returns any available subset of:
      - mission_type
      - mission_objective
      - mission_start_time
    """
    text = _read_eng_briefing_text(game_dir, campaign_name, mission_id, mission_file=mission_file)
    if not text:
        return {}

    result: dict = {}

    mission_type_match = _ENG_MISSION_TYPE_RE.search(text)
    if mission_type_match:
        mission_type = _normalize_briefing_value(mission_type_match.group(1))
        if mission_type:
            result["mission_type"] = mission_type

    objective_match = (
        _ENG_ORDERS_RE.search(text)
        or _ENG_FLIGHT_MISSION_RE.search(text)
        or _ENG_MISSION_RE.search(text)
    )
    if objective_match:
        mission_objective = _normalize_briefing_value(objective_match.group(1))
        if mission_objective:
            result["mission_objective"] = mission_objective

    time_match = _ENG_TIME_RE.search(text)
    if time_match:
        mission_start_time = _normalize_briefing_value(time_match.group(1))
        if mission_start_time:
            result["mission_start_time"] = mission_start_time

    return result


def read_eng_weather(
    game_dir: str,
    campaign_name: str,
    mission_id: str,
    mission_file: str = "",
) -> Optional[dict]:
    """
    Extract the weather description from a campaign mission's .eng briefing file.

    The .eng file is UTF-16 encoded.  The weather line is embedded in the
    mission briefing text, separated by HTML <br> tags, e.g.:
        "Weather: moderately overcast, 2,500 m cloud base<br>"
        "Weather: 13°C, Clouds: Scattered clouds at 800m."

    Returns a dict with 'conditions' and 'summary' set to the raw briefing
    text, or None when the file is absent or contains no Weather line.
    """
    text = _read_eng_briefing_text(game_dir, campaign_name, mission_id, mission_file=mission_file)
    if text:
        m = _ENG_WEATHER_RE.search(text)
        if m:
            weather_str = _normalize_briefing_value(m.group(1))
            if weather_str:
                LOGGER.debug("Eng weather %s/%s: %r", campaign_name, mission_id, weather_str)
                return {
                    "conditions": weather_str,
                    "summary": weather_str,
                    "source": "mission_briefing",
                }
    return None


# ---------------------------------------------------------------------------
# msnbin landscape extraction
# ---------------------------------------------------------------------------

_LANDSCAPE_RE = re.compile(rb"LANDSCAPE[_\-]([A-Za-z][A-Za-z0-9_\-]{2,})", re.IGNORECASE)


def read_msnbin_landscape(msnbin_path: Path) -> Optional[str]:
    """
    Read the first 1 KB of a .msnbin file and return the LANDSCAPE token,
    e.g. 'LANDSCAPE_Kuban_a' → returns 'Kuban_a', or None if not found.
    """
    try:
        with open(msnbin_path, "rb") as fh:
            header = fh.read(1024)
        m = _LANDSCAPE_RE.search(header)
        if m:
            return m.group(1).decode("ascii", errors="replace")
    except OSError as exc:
        LOGGER.debug("Cannot read %s: %s", msnbin_path, exc)
    return None


def _landscape_to_coords(landscape_suffix: str) -> Optional[Tuple[float, float, str]]:
    """
    Map a LANDSCAPE suffix (e.g. 'Kuban_a', 'Stalin_s', 'westernfront_sp')
    to (lat, lon, place_name) by substring-matching against _IL2_LOCATIONS.
    """
    lower = landscape_suffix.lower()
    # Try longest-match substring
    matched = [(kw, v) for kw, v in _IL2_LOCATIONS.items() if kw in lower]
    if matched:
        kw, coords = max(matched, key=lambda x: len(x[0]))
        LOGGER.debug("Landscape %r matched keyword %r → %s", landscape_suffix, kw, coords[2])
        return coords
    return None


def resolve_mission_coordinates(
    game_dir: str, campaign_name: str, mission_id: str
) -> Optional[Tuple[float, float, str, str]]:
    """
    Return (lat, lon, place_name, landscape_suffix) for a specific mission by reading
    its .msnbin file header.  Use this for per-mission resolution in multi-map campaigns.

    Returns None if the msnbin cannot be found or the landscape is unrecognised.
    Does NOT use spawn position — returns the map centre for the mission's landscape.
    Per-mission cache keyed by (campaign_name, mission_id).
    """
    cache_key = f"mission|{campaign_name.lower()}|{mission_id.lower()}"
    if cache_key in _campaign_coords_cache:
        result = _campaign_coords_cache[cache_key]
        return result  # type: ignore[return-value]

    result: Optional[Tuple[float, float, str, str]] = None
    if game_dir:
        msnbin = Path(game_dir) / "data" / "Campaigns" / campaign_name / f"{mission_id}.msnbin"
        if not msnbin.exists():
            msnbin = Path(game_dir) / "data" / "Campaigns" / campaign_name / f"{mission_id}.cmpbin"
        if msnbin.exists():
            landscape = read_msnbin_landscape(msnbin)
            if landscape:
                coords = _landscape_to_coords(landscape)
                if coords:
                    lat, lon, place = coords
                    result = (lat, lon, place, landscape)
                    LOGGER.info(
                        "Mission %s/%s: map=%r → %s (%.2f°N %.2f°E)",
                        campaign_name, mission_id, landscape, place, lat, lon,
                    )

    _campaign_coords_cache[cache_key] = result  # type: ignore[assignment]
    return result


def resolve_campaign_coordinates(game_dir: str, campaign_name: str) -> Optional[Tuple[float, float, str]]:
    """
    Return (lat, lon, place_name) for a campaign by reading its .msnbin files.

    Priority:
      1. Read LANDSCAPE_* from the first .msnbin in
         <game_dir>/data/Campaigns/<campaign_name>/
      2. Keyword-match on campaign_name
      3. Geocoding fallback on campaign_name

    Result is cached per campaign_name for the server lifetime.
    """
    cache_key = campaign_name.lower().strip()
    if cache_key in _campaign_coords_cache:
        return _campaign_coords_cache[cache_key]

    coords: Optional[Tuple[float, float, str]] = None

    # --- 1. msnbin landscape ---
    if game_dir:
        campaigns_dir = Path(game_dir) / "data" / "Campaigns" / campaign_name
        if not campaigns_dir.exists():
            # Case-insensitive fallback (Windows FS is usually case-insensitive but be safe)
            parent = Path(game_dir) / "data" / "Campaigns"
            if parent.exists():
                for d in parent.iterdir():
                    if d.name.lower() == campaign_name.lower() and d.is_dir():
                        campaigns_dir = d
                        break

        if campaigns_dir.exists():
            msnbin_files = sorted(campaigns_dir.glob("*.msnbin"))
            for msnbin_path in msnbin_files:
                landscape = read_msnbin_landscape(msnbin_path)
                if landscape:
                    coords = _landscape_to_coords(landscape)
                    if coords:
                        LOGGER.info(
                            "Campaign %r: map=%r → %s (%.2f°N %.2f°E)",
                            campaign_name, landscape, coords[2], coords[0], coords[1],
                        )
                        break
                    else:
                        LOGGER.debug("Campaign %r: landscape %r — no coordinate match", campaign_name, landscape)
                    break  # only need the first .msnbin

    # --- 2. keyword fallback on campaign name ---
    if coords is None:
        coords = _keyword_resolve(campaign_name)
        if coords:
            LOGGER.debug("Campaign %r: resolved via keyword match → %s", campaign_name, coords[2])

    _campaign_coords_cache[cache_key] = coords
    return coords


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _keyword_resolve(hint: str) -> Optional[Tuple[float, float, str]]:
    """Keyword + geocoding resolution (no caching — callers cache)."""
    lower = hint.lower().strip()
    if lower in _IL2_LOCATIONS:
        return _IL2_LOCATIONS[lower]
    matched = [(kw, v) for kw, v in _IL2_LOCATIONS.items() if kw in lower]
    if matched:
        kw, coords = max(matched, key=lambda x: len(x[0]))
        return coords
    return _geocode(hint)


def _geocode(name: str) -> Optional[Tuple[float, float, str]]:
    params = urllib.parse.urlencode({
        "name": name, "count": 1, "language": "en", "format": "json",
    })
    data = _fetch_json(f"https://geocoding-api.open-meteo.com/v1/search?{params}", timeout=5)
    if data:
        results = data.get("results") or []
        if results:
            r = results[0]
            return float(r["latitude"]), float(r["longitude"]), r.get("name", name)
    return None


def _fetch_json(url: str, timeout: int = 8) -> Optional[dict]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError as exc:
        LOGGER.warning("HTTP request failed: %s — %s", url, exc)
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Unexpected error fetching %s: %s", url, exc)
    return None


def _fetch_daily_weather(lat: float, lon: float, date_str: str) -> Optional[dict]:
    params = urllib.parse.urlencode({
        "latitude": f"{lat:.4f}",
        "longitude": f"{lon:.4f}",
        "start_date": date_str,
        "end_date": date_str,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max,weather_code",
        "wind_speed_unit": "kmh",
        "timezone": "UTC",
    })
    data = _fetch_json(f"https://archive-api.open-meteo.com/v1/archive?{params}", timeout=5)
    if not data:
        return None
    daily = data.get("daily") or {}
    times = daily.get("time") or []
    if not times:
        return None

    def _at(key: str):
        arr = daily.get(key) or []
        return arr[0] if arr else None

    return {
        "temp_max":         _at("temperature_2m_max"),
        "temp_min":         _at("temperature_2m_min"),
        "precipitation_mm": _at("precipitation_sum"),
        "wind_kmh":         _at("wind_speed_10m_max"),
        "weather_code":     _at("weather_code"),
    }


def _build_summary(raw: dict, place_name: str) -> dict:
    code = raw.get("weather_code")
    condition = _WMO_CODES.get(int(code), "variable conditions") if code is not None else "variable conditions"
    t_max = raw.get("temp_max")
    t_min = raw.get("temp_min")
    precip = raw.get("precipitation_mm")
    wind = raw.get("wind_kmh")

    parts: list[str] = []
    if t_min is not None and t_max is not None:
        parts.append(f"Temperature {t_min:.0f}°C to {t_max:.0f}°C")
    elif t_max is not None:
        parts.append(f"Temperature ~{t_max:.0f}°C")
    parts.append(condition.capitalize())
    if precip and precip > 0:
        parts.append(f"{precip:.1f} mm precipitation")
    if wind:
        parts.append(f"Wind {wind:.0f} km/h")

    return {
        "location":          place_name,
        "conditions":        condition,
        "temperature_min_c": round(t_min, 1) if t_min is not None else None,
        "temperature_max_c": round(t_max, 1) if t_max is not None else None,
        "precipitation_mm":  round(precip, 1) if precip is not None else None,
        "wind_kmh":          round(wind, 0) if wind is not None else None,
        "summary":           "; ".join(parts),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def lookup_historical_weather_by_coords(
    lat: float, lon: float, place_name: str, date_str: str
) -> Optional[dict]:
    """
    Fetch weather for explicit coordinates. Use when the caller has already
    resolved coordinates (e.g. via resolve_campaign_coordinates).
    """
    try:
        if int(date_str[:4]) < 1940:
            return None
    except (ValueError, IndexError):
        return None

    cache_key = f"{lat:.4f},{lon:.4f}|{date_str}"
    if cache_key in _weather_cache:
        return _weather_cache[cache_key]

    LOGGER.info("Weather lookup: %s (%.2f°N %.2f°E) on %s", place_name, lat, lon, date_str)
    raw = _fetch_daily_weather(lat, lon, date_str)
    if raw is None:
        _weather_cache[cache_key] = None
        return None

    result = _build_summary(raw, place_name)
    LOGGER.info("Weather result: %s", result["summary"])
    _weather_cache[cache_key] = result
    return result


def lookup_historical_weather(location_hint: str, date_str: str) -> Optional[dict]:
    """
    Resolve *location_hint* via keyword/geocoding and return a weather summary.
    Use for career mode (infoId / squadron name). For campaigns prefer
    resolve_campaign_coordinates() + lookup_historical_weather_by_coords().
    """
    if not location_hint or not date_str:
        return None
    try:
        if int(date_str[:4]) < 1940:
            return None
    except (ValueError, IndexError):
        return None

    coords = _keyword_resolve(location_hint)
    if coords is None:
        LOGGER.debug("Cannot resolve coordinates for %r", location_hint)
        return None

    lat, lon, place_name = coords
    return lookup_historical_weather_by_coords(lat, lon, place_name, date_str)
