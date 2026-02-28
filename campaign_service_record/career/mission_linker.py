"""
MissionReportLinker: matches cp.db mission rows to missionReport text files.

Career missions use a generic name (MFile:Missions_gen.msnbin) so the filename
cannot be used to locate the report. Instead, a 3-step algorithm is used:

    STEP 1 — Date filter
        Derive a date string from mission.insDate.
        Glob for missionReport(YYYY-MM-DD_*.txt) in the reports directory.

    STEP 2 — Header match
        Parse GDate and GTime from each candidate file header.
        Match exactly against mission.startTime.

    STEP 3 — Duration verification (safeguard)
        Read the last T: entry in the matched file.
        duration_seconds = T / 50   (IL-2 runs at 50 ticks/second)
        estimated_end = startTime + duration_seconds
        Compare against mission.endTime (±30 s tolerance).
        Reject the file if duration is implausible.

MissionReport files are used ONLY for sortie debriefing and narrative
reconstruction. Statistics must never be derived from these files.

The report format is confirmed to be identical to Campaign mode reports,
so the same parsing logic applies.
"""

import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

import sqlite3

logger = logging.getLogger(__name__)

# IL-2 simulation tick rate: 50 ticks per second
_TICKS_PER_SECOND = 50

# Tolerance for duration verification (seconds)
_DURATION_TOLERANCE_SECONDS = 30


class MissionReportLinker:
    """
    Matches cp.db mission rows to missionReport log files using a 3-step algorithm.

    Used exclusively for sortie debriefing and narrative text.
    Statistics are never derived from these files.
    """

    def __init__(self, reports_dir: Path):
        self._reports_dir = reports_dir

    def find_report(self, mission_row: sqlite3.Row) -> Optional[Path]:
        """
        Locate the missionReport file for a given mission row.

        Args:
            mission_row: sqlite3.Row from the mission table.

        Returns:
            Path to the matched missionReport file, or None if no match found.
        """
        try:
            ins_date = self._parse_datetime(mission_row["insDate"])
            start_time = self._parse_datetime(mission_row["startTime"])
            end_time_raw = mission_row["endTime"]
        except (KeyError, TypeError) as exc:
            logger.warning("Cannot link report: missing mission row fields: %s", exc)
            return None

        if ins_date is None or start_time is None:
            logger.debug("Mission row missing insDate or startTime; cannot link report")
            return None

        # Step 1: collect candidates by date
        candidates = self._candidates_by_date(ins_date)
        if not candidates:
            logger.debug("No missionReport candidates for date %s", ins_date.date())
            return None

        # Step 2 + 3: match by header, verify duration
        for candidate in candidates:
            report_start = self._parse_report_header(candidate)
            if report_start is None:
                continue
            if report_start != start_time:
                continue
            # Header matched — verify duration
            if self._verify_duration(candidate, start_time, end_time_raw):
                logger.debug("Linked mission to report: %s", candidate.name)
                return candidate
            else:
                logger.warning(
                    "Header matched %s but duration verification failed; skipping",
                    candidate.name
                )

        logger.debug(
            "No missionReport matched for mission startTime=%s",
            start_time.isoformat() if start_time else "unknown"
        )
        return None

    def extract_debriefing_html(self, report_path: Path) -> str:
        """
        Return the raw text content of a matched missionReport file.

        The content is passed to the existing debriefing HTML renderer.
        Since the report format is confirmed identical to Campaign mode,
        the same downstream parsing applies.

        Returns empty string on read error.
        """
        try:
            return report_path.read_text(encoding='utf-8', errors='replace')
        except OSError as exc:
            logger.error("Cannot read report %s: %s", report_path, exc)
            return ''

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _candidates_by_date(self, ins_date: datetime) -> List[Path]:
        """Glob for missionReport files matching the given date.

        Returns files sorted by modification time descending so that the most
        recent attempt (the one whose startTime cp.db records) is tried first.
        """
        date_str = ins_date.strftime("%Y-%m-%d")
        # Filename format: missionReport(YYYY-MM-DD_HH-MM-SS).txt
        pattern = f"missionReport({date_str}_*.txt"
        results = list(self._reports_dir.glob(pattern))
        if not results:
            # Also search one level deep (reports may be in per-campaign subdirectories)
            results = list(self._reports_dir.rglob(pattern))
        # Sort by mtime descending: latest-attempt file is tried first,
        # matching the startTime that cp.db records for the final attempt.
        return sorted(results, key=lambda p: p.stat().st_mtime, reverse=True)

    def _parse_report_header(self, path: Path) -> Optional[datetime]:
        """
        Parse GDate and GTime from a missionReport file header.

        Returns combined datetime or None if parsing fails.
        """
        gdate: Optional[str] = None
        gtime: Optional[str] = None
        try:
            with open(path, encoding='utf-8', errors='replace') as fh:
                for line in fh:
                    stripped = line.strip()
                    if stripped.startswith("GDate:"):
                        gdate = stripped.split(":", 1)[1].strip()
                    elif stripped.startswith("GTime:"):
                        gtime = stripped.split(":", 1)[1].strip()
                    if gdate and gtime:
                        break
        except OSError as exc:
            logger.debug("Cannot read candidate %s: %s", path.name, exc)
            return None

        if not gdate or not gtime:
            return None

        combined = f"{gdate} {gtime}"
        for fmt in ("%Y.%m.%d %H:%M:%S", "%d.%m.%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(combined, fmt)
            except ValueError:
                continue

        logger.debug("Unrecognised GDate/GTime format in %s: '%s'", path.name, combined)
        return None

    def _verify_duration(
        self,
        path: Path,
        start_time: datetime,
        end_time_raw
    ) -> bool:
        """
        Verify that the report's duration is consistent with mission.endTime.

        Reads the last T: entry in the file.
        duration_seconds = T_value / 50
        estimated_end    = start_time + timedelta(seconds=duration_seconds)
        Tolerance: ±30 seconds.
        """
        end_time = self._parse_datetime(end_time_raw)
        if end_time is None:
            # Cannot verify — accept the match (header already confirmed)
            return True

        last_t = self._read_last_t_value(path)
        if last_t is None:
            # Cannot verify — accept the match
            return True

        duration_seconds = last_t / _TICKS_PER_SECOND
        estimated_end = start_time + timedelta(seconds=duration_seconds)
        delta = abs((estimated_end - end_time).total_seconds())
        return delta <= _DURATION_TOLERANCE_SECONDS

    @staticmethod
    def _read_last_t_value(path: Path) -> Optional[int]:
        """Read the last T:<int> entry from a missionReport file."""
        _T_RE = re.compile(r'^T:(\d+)')
        last_t: Optional[int] = None
        try:
            with open(path, encoding='utf-8', errors='replace') as fh:
                for line in fh:
                    m = _T_RE.match(line.strip())
                    if m:
                        last_t = int(m.group(1))
        except OSError:
            return None
        return last_t

    @staticmethod
    def _parse_datetime(raw) -> Optional[datetime]:
        """
        Parse a value from a cp.db date/time column to a datetime object.

        Handles:
            - Unix timestamp (int/float)
            - ISO string "YYYY-MM-DD HH:MM:SS"
            - ISO string "YYYY-MM-DDTHH:MM:SS"
            - Date-only string "YYYY-MM-DD"
        """
        if raw is None:
            return None
        if isinstance(raw, (int, float)):
            try:
                return datetime.fromtimestamp(raw)
            except (OSError, OverflowError, ValueError):
                return None
        if isinstance(raw, str):
            for fmt in (
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d",
                "%Y.%m.%d %H:%M:%S",
            ):
                try:
                    return datetime.strptime(raw, fmt)
                except ValueError:
                    continue
        return None
