"""
CareerDebriefingManager: generates mission debriefing HTML for career mode.

Architecture:
    For each theatre segment in the career chain, retrieves missions from cp.db
    that the player flew, links each to its missionReport .txt file, parses with
    MissionDebriefParser (il2_mission_debrief), and caches the per-mission HTML.

    Theatre sections are rendered as native <details>/<summary> collapsible blocks.
    HTML labels are English; frontend localizeDebriefingsHtml() translates them.

Report matching strategy:
    cp.db stores IN-GAME dates in mission.startTime and REAL-WORLD Unix timestamps
    in mission.insDate.  IL-2 names missionReport files with REAL-WORLD dates:
        missionReport(2025-02-15_14-30-00).mlg
    IL-2 writes binary .mlg files only; .txt files only exist after mlg2txt
    conversion.  For each mission, MissionReportLinker.find_career_report():
        1. Globs .mlg files whose filename date is within ±1 day of insDate
           (covers UTC vs local-time differences stored in cp.db).
        2. Converts each candidate to .txt via mlg2txt subprocess (skips if .txt
           already up-to-date).
        3. Parses the GDate/GTime header from the .txt (which is the IN-GAME date).
        4. Matches against mission.startTime; verifies duration.
    Only the matched .txt is parsed for event HTML.

Cache layout:
    <cache_dir>/career/<root_career_id>/cache_index.json
    {
        "<mission_id>": {
            "report_path": "str",
            "report_mtime": float | null,
            "html": "str",
            "duration_seconds": float | null,
            "linked": bool
        }
    }
"""

import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import sqlite3

from campaign_service_record.career.database import CareerDatabase
from campaign_service_record.career.chain_resolver import VirtualPilotCareer
from campaign_service_record.career.mission_linker import MissionReportLinker

logger = logging.getLogger(__name__)

# Maximum events rendered per mission box (matches campaign tracker limit)
_MAX_EVENTS = 25


@dataclass
class _MissionResult:
    """Per-mission processing result (internal)."""
    mission_id: int
    career_id: int
    theatre_label: str
    mission_date: str
    html: str
    duration_seconds: Optional[float]
    linked: bool


class CareerDebriefingManager:
    """
    Builds theatre-grouped mission debriefing HTML for a single career.

    Args:
        db:        CareerDatabase instance.
        career:    VirtualPilotCareer for the target pilot.
        linker:    MissionReportLinker pointed at the game reports directory.
        cache_dir: Root directory for debriefing cache files.
    """

    def __init__(
        self,
        db: CareerDatabase,
        career: VirtualPilotCareer,
        linker: MissionReportLinker,
        cache_dir: Path,
    ):
        self._db = db
        self._career = career
        self._linker = linker
        self._cache_path = (
            cache_dir / "career" / str(career.root_career_id) / "cache_index.json"
        )
        self._results: Optional[List[_MissionResult]] = None  # lazily computed

        # Resolve mlg2txt converter path for career report linking.
        # In frozen mode: mlg2txt.exe sits next to the EXE.
        # In dev mode: mlg2txt.py lives at the repo root (three levels up from
        # this file: career/ → campaign_service_record/ → repo root).
        if getattr(sys, 'frozen', False):
            _candidate = Path(sys.executable).parent / 'mlg2txt.exe'
        else:
            _candidate = Path(__file__).parent.parent.parent / 'mlg2txt.py'
        self._mlg2txt_path: Optional[Path] = _candidate if _candidate.exists() else None
        if self._mlg2txt_path is None:
            logger.warning("mlg2txt not found at %s; .mlg conversion unavailable", _candidate)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_debriefings_html(self) -> str:
        """
        Build theatre-grouped debriefing HTML string.

        Returns:
            HTML string ready for injection into the debriefings container,
            or empty string if no missions exist.
        """
        results = self._get_results()
        if not results:
            return ""

        # Group by career_id preserving chain order
        theatre_order: List[Tuple[int, str]] = []
        by_theatre: Dict[int, List[_MissionResult]] = {}
        for r in results:
            if r.career_id not in by_theatre:
                theatre_order.append((r.career_id, r.theatre_label))
                by_theatre[r.career_id] = []
            by_theatre[r.career_id].append(r)

        parts = []
        for career_id, label in theatre_order:
            missions = by_theatre[career_id]
            inner = "\n".join(m.html for m in missions)
            parts.append(
                f'<details open class="theatre-section">\n'
                f'  <summary class="theatre-header">{label}</summary>\n'
                f'  <div class="theatre-missions">\n{inner}\n  </div>\n'
                f'</details>'
            )
        return "\n".join(parts)

    def get_mission_stats(self) -> Dict:
        """
        Return a missions_stats dict for injection into the career summary.

        Keys match the shape expected by _build_summary() / renderSummary().
        """
        results = self._get_results()
        total = len(results)

        durations = [
            r.duration_seconds
            for r in results
            if r.linked and r.duration_seconds is not None
        ]
        total_seconds = sum(durations)
        avg_seconds = total_seconds / len(durations) if durations else 0.0

        return {
            "total_missions": total,
            "completed_missions": total,
            "successful_missions": total,
            "success_rate": 100 if total else 0,
            "total_flight_time": _format_duration(total_seconds),
            "average_duration": _format_duration(avg_seconds),
            "landings": [],
        }

    # ------------------------------------------------------------------
    # Private: processing pipeline
    # ------------------------------------------------------------------

    def _get_results(self) -> List[_MissionResult]:
        """Return processed mission results, computing lazily on first call."""
        if self._results is None:
            self._results = self._process_all_missions()
        return self._results

    def _process_all_missions(self) -> List[_MissionResult]:
        """Process all missions across all theatre segments in chain order."""
        cache = self._load_cache()
        results: List[_MissionResult] = []
        mission_num = 0
        cache_dirty = False

        for i, career_row in enumerate(self._career.chain):
            career_id = int(career_row["id"])
            player_id = int(career_row["playerId"])
            label = (
                self._career.theatre_labels[i]
                if i < len(self._career.theatre_labels)
                else f"Theatre {i + 1}"
            )
            missions = self._db.get_missions_for_career(career_id, player_id)

            for mission_row in missions:
                mission_num += 1
                result, updated = self._process_one_mission(
                    mission_row, career_id, label, mission_num, cache
                )
                results.append(result)
                if updated:
                    cache_dirty = True

        if cache_dirty:
            self._save_cache(cache)

        return results

    def _process_one_mission(
        self,
        mission_row: sqlite3.Row,
        career_id: int,
        theatre_label: str,
        mission_num: int,
        cache: Dict,
    ) -> Tuple[_MissionResult, bool]:
        """
        Process a single mission row.

        Mutates ``cache`` in-place when a new entry is written.

        Returns:
            (result, cache_was_updated) tuple.
        """
        mission_id = int(mission_row["id"])
        mission_date = _format_mission_date(mission_row)
        cache_key = str(mission_id)

        # --- Cache hit check ---
        cached = cache.get(cache_key)
        if cached and cached.get("linked"):
            report_path_str = cached.get("report_path", "")
            cached_mtime = cached.get("report_mtime")
            if report_path_str and cached_mtime is not None:
                try:
                    current_mtime = Path(report_path_str).stat().st_mtime
                    if abs(current_mtime - cached_mtime) < 1.0:
                        return _MissionResult(
                            mission_id=mission_id,
                            career_id=career_id,
                            theatre_label=theatre_label,
                            mission_date=mission_date,
                            html=cached["html"],
                            duration_seconds=cached.get("duration_seconds"),
                            linked=True,
                        ), False
                except OSError:
                    pass  # File gone — fall through and re-link

        # --- Attempt to link missionReport via .mlg scan ---
        # mission.insDate is a real-world timestamp used to find candidate .mlg
        # files by filename date (±1 day for timezone differences).  Each
        # candidate is converted to .txt and its GDate/GTime header is matched
        # against mission.startTime (in-game date).
        report_path = self._linker.find_career_report(
            mission_row, self._mlg2txt_path
        )
        if report_path is None:
            logger.debug(
                "No missionReport linked for mission id=%d (startTime=%s)",
                mission_id, mission_row["startTime"],
            )
            return _MissionResult(
                mission_id=mission_id,
                career_id=career_id,
                theatre_label=theatre_label,
                mission_date=mission_date,
                html=_render_stub_html(mission_num, mission_date),
                duration_seconds=None,
                linked=False,
            ), False

        # --- Parse report ---
        data = _parse_report(report_path)
        if data is None:
            return _MissionResult(
                mission_id=mission_id,
                career_id=career_id,
                theatre_label=theatre_label,
                mission_date=mission_date,
                html=_render_stub_html(mission_num, mission_date),
                duration_seconds=None,
                linked=False,
            ), False

        duration_seconds = _parse_duration_seconds(
            data.get("summary", {}).get("flight_duration", "")
        )
        html = _render_mission_html(data, mission_num, mission_date)

        try:
            report_mtime: Optional[float] = report_path.stat().st_mtime
        except OSError:
            report_mtime = None

        cache[cache_key] = {
            "report_path": str(report_path),
            "report_mtime": report_mtime,
            "html": html,
            "duration_seconds": duration_seconds,
            "linked": True,
        }

        return _MissionResult(
            mission_id=mission_id,
            career_id=career_id,
            theatre_label=theatre_label,
            mission_date=mission_date,
            html=html,
            duration_seconds=duration_seconds,
            linked=True,
        ), True

    # ------------------------------------------------------------------
    # Private: cache I/O
    # ------------------------------------------------------------------

    def _load_cache(self) -> Dict:
        if not self._cache_path.exists():
            return {}
        try:
            return json.loads(self._cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Career debrief cache unreadable (%s); starting fresh", exc)
            return {}

    def _save_cache(self, cache: Dict) -> None:
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._cache_path.write_text(
                json.dumps(cache, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.warning("Failed to save career debrief cache: %s", exc)


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _parse_report(report_path: Path) -> Optional[Dict]:
    """
    Parse a missionReport .txt file using il2_mission_debrief.MissionDebriefParser.

    Lazy-imports il2_mission_debrief to avoid argparse side effects at module load.
    Saves a .events.json sidecar next to the report for reuse by downstream tools.

    Returns:
        Parsed data dict with keys player, summary, events; or None on failure.
    """
    try:
        import il2_mission_debrief  # noqa: PLC0415 — intentional lazy import
        parser = il2_mission_debrief.MissionDebriefParser(report_path, verbose=False)
        parser.parse()
        json_path = report_path.with_suffix(".events.json")
        parser.to_json(json_path)
        if not json_path.exists():
            logger.warning(
                "MissionDebriefParser produced no JSON for %s", report_path.name
            )
            return None
        return json.loads(json_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed to parse %s: %s", report_path.name, exc)
        return None


def _render_mission_html(data: Dict, mission_num: int, mission_date: str) -> str:
    """
    Render a mission-box HTML block from parsed debrief data.

    Produces English labels matching the patterns replaced by
    detail.js localizeDebriefingsHtml() for client-side translation.
    """
    summary = data.get("summary", {})
    player = data.get("player", {})
    events = data.get("events", [])

    aircraft = player.get("aircraft", "Unknown")
    duration = summary.get("flight_duration", "—")
    status = summary.get("final_state", "—")
    aircraft_dmg = int(summary.get("aircraft_damage", 0) or 0)
    pilot_dmg = int(summary.get("pilot_damage", 0) or 0)

    lines: List[str] = [f'<div class="mission-box">']
    lines.append(f"<b>MISSION {mission_num}</b> &mdash; {mission_date}<br>")

    summary_parts = [
        f"Aircraft: {aircraft}",
        f"Duration: {duration}",
        f"Status: {status}",
    ]
    if aircraft_dmg > 0:
        summary_parts.append(f"Aircraft Dmg: {aircraft_dmg}%")
    if pilot_dmg > 0:
        summary_parts.append(f"Pilot Dmg: {pilot_dmg}%")
    lines.append(" | ".join(summary_parts) + "<br>")
    lines.append("<br>")
    lines.append("<b>FLIGHT LOG</b><br>")

    mission_ended_in_bailout = "Bailout" in str(status)

    for event in events[:_MAX_EVENTS]:
        time_str = event.get("time", "")
        event_type = event.get("type", event.get("event", ""))
        target = event.get("target", "")
        altitude = event.get("altitude")

        if event_type == "Kill":
            alt_str = f" (Alt: {altitude}m)" if altitude else ""
            lines.append(f"{time_str}&nbsp;&nbsp;{target} destroyed{alt_str}<br>")
        elif event_type == "Damage Taken":
            if mission_ended_in_bailout:
                continue
            if event.get("attacker_unknown") or not target:
                lines.append(f"{time_str}&nbsp;&nbsp;Damage taken<br>")
            else:
                lines.append(f"{time_str}&nbsp;&nbsp;Hit by {target}<br>")
        else:
            lines.append(f"{time_str}&nbsp;&nbsp;{event_type}<br>")

    lines.append("</div>")
    return "\n".join(lines)


def _render_stub_html(mission_num: int, mission_date: str) -> str:
    """Minimal mission-box for missions with no linked report."""
    return (
        f'<div class="mission-box">'
        f"<b>MISSION {mission_num}</b> &mdash; {mission_date}<br>"
        f"<i>No flight log available</i>"
        f"</div>"
    )


def _format_mission_date(mission_row: sqlite3.Row) -> str:
    """Format mission.startTime as a localizable date string (e.g. '12 September 1942')."""
    dt = MissionReportLinker._parse_datetime(mission_row["startTime"])
    if dt is None:
        return "Unknown date"
    return dt.strftime("%d %B %Y")


def _parse_duration_seconds(duration_str: str) -> Optional[float]:
    """Parse 'HH:MM:SS' to total seconds, or None on failure."""
    if not duration_str:
        return None
    parts = str(duration_str).split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
    except (ValueError, IndexError):
        pass
    return None


def _format_duration(total_seconds: float) -> str:
    """Format total seconds to 'HH:MM' string for summary display."""
    secs = int(total_seconds)
    return f"{secs // 3600:02d}:{(secs % 3600) // 60:02d}"
