"""
MissionReportLinker: matches cp.db mission rows to missionReport log files.

Campaign mode — 3-step algorithm using .txt files:
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

Career mode — find_career_report():
    IL-2 writes only binary .mlg files to FlightLogs; there are no .txt files
    unless they have been converted by mlg2txt.  cp.db stores:
        mission.insDate   — real-world timestamp (may differ from the missionReport
                            filename date by up to ±1 day due to timezone offsets
                            between cp.db UTC and local filename time)
        mission.startTime — IN-GAME date/time (e.g. "1941.09.27 07:24:34");
                            this matches GDate/GTime in the report AType:0 record.
    Algorithm:
        1. Parse insDate as a real-world datetime.
        2. Glob for .mlg files whose filename date is within ±1 day of insDate.
        3. For each candidate (newest mtime first):
              a. If <stem>[0].txt already exists and is newer than the .mlg, use it.
              b. Otherwise convert via mlg2txt subprocess → <stem>[0].txt.
              c. Parse GDate/GTime tokens from the AType:0 record in the .txt.
              d. If it matches mission.startTime exactly, this is our file.
        4. Return the matched .txt path, or None.

MissionReport files are used ONLY for sortie debriefing and narrative
reconstruction. Statistics must never be derived from these files.
"""

import logging
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

import sqlite3

logger = logging.getLogger(__name__)

# IL-2 simulation tick rate: 50 ticks per second
_TICKS_PER_SECOND = 50

# Tolerance for duration verification (seconds)
_DURATION_TOLERANCE_SECONDS = 30

# Search window (days) around insDate when scanning .mlg candidates.
# Covers UTC vs local-time mismatches stored in cp.db.
_MLG_DATE_WINDOW_DAYS = 1


class MissionReportLinker:
    """
    Matches cp.db mission rows to missionReport log files.

    Used exclusively for sortie debriefing and narrative text.
    Statistics are never derived from these files.
    """

    def __init__(self, reports_dir: Path):
        self._reports_dir = reports_dir

    # ------------------------------------------------------------------
    # Campaign mode: txt-based matching
    # ------------------------------------------------------------------

    def find_report(self, mission_row: sqlite3.Row) -> Optional[Path]:
        """
        Locate the missionReport .txt file for a given mission row.
        Intended for campaign mode where IL-2 writes .txt files directly.

        Args:
            mission_row: sqlite3.Row from the mission table.

        Returns:
            Path to the matched missionReport .txt file, or None.
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

        candidates = self._candidates_by_date(ins_date)
        if not candidates:
            logger.debug("No missionReport candidates for date %s", ins_date.date())
            return None

        for candidate in candidates:
            report_start = self._parse_report_header(candidate)
            if report_start is None:
                continue
            if report_start != start_time:
                continue
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

    # ------------------------------------------------------------------
    # Career mode: mlg-based matching
    # ------------------------------------------------------------------

    def find_career_report(
        self,
        mission_row: sqlite3.Row,
        mlg2txt_path: Optional[Path] = None,
    ) -> Optional[Path]:
        """
        Find and convert the missionReport .mlg for a career mission.

        Args:
            mission_row:  sqlite3.Row from the mission table.
            mlg2txt_path: Path to mlg2txt.exe (frozen) or mlg2txt.py (dev).
                          If None, only pre-converted .txt files are used.

        Returns:
            Path to the matched .txt file, or None if no match found.
        """
        try:
            ins_date = self._parse_datetime(mission_row["insDate"])
            start_time = self._parse_datetime(mission_row["startTime"])
            end_time_raw = mission_row["endTime"]
        except (KeyError, TypeError) as exc:
            logger.warning("Cannot link career report: missing fields: %s", exc)
            return None

        if ins_date is None or start_time is None:
            logger.debug("Career mission row missing insDate or startTime; cannot link")
            return None

        # Primary search: ±1 day window around insDate (covers timezone offsets).
        candidates = self._candidates_mlg_by_date(ins_date)
        result = self._match_from_candidates(candidates, start_time, end_time_raw, mlg2txt_path)
        if result is not None:
            return result

        # Fallback: insDate is a batch-save time and may not reflect the actual
        # flight date.  Scan all .mlg files in the directory.
        all_mlg = sorted(
            self._reports_dir.rglob("missionReport(*.mlg"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        fallback_candidates = [p for p in all_mlg if p not in set(candidates)]
        if fallback_candidates:
            logger.debug(
                "±%d day window missed startTime=%s; falling back to full scan (%d files)",
                _MLG_DATE_WINDOW_DAYS, start_time.isoformat(), len(fallback_candidates),
            )
            result = self._match_from_candidates(
                fallback_candidates, start_time, end_time_raw, mlg2txt_path
            )

        if result is None:
            logger.debug(
                "No career missionReport matched for startTime=%s",
                start_time.isoformat(),
            )
        return result

    # ------------------------------------------------------------------
    # Shared utility
    # ------------------------------------------------------------------

    def extract_debriefing_html(self, report_path: Path) -> str:
        """
        Return the raw text content of a matched missionReport file.

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
        """Glob for missionReport .txt files matching the given date (mtime desc)."""
        date_str = ins_date.strftime("%Y-%m-%d")
        pattern = f"missionReport({date_str}_*.txt"
        results = list(self._reports_dir.glob(pattern))
        if not results:
            results = list(self._reports_dir.rglob(pattern))
        return sorted(results, key=lambda p: p.stat().st_mtime, reverse=True)

    def _match_from_candidates(
        self,
        candidates: List[Path],
        start_time: datetime,
        end_time_raw,
        mlg2txt_path: Optional[Path],
    ) -> Optional[Path]:
        """Try each .mlg candidate; return first .txt whose GDate/GTime matches start_time."""
        for mlg_path in candidates:
            txt_path = self._ensure_txt(mlg_path, mlg2txt_path)
            if txt_path is None:
                continue
            report_start = self._parse_report_header(txt_path)
            if report_start is None:
                continue
            if report_start != start_time:
                continue
            if self._verify_duration(txt_path, start_time, end_time_raw):
                logger.debug("Career report linked: %s → %s", mlg_path.name, txt_path.name)
                return txt_path
            else:
                logger.warning(
                    "Header matched %s but duration verification failed; skipping",
                    txt_path.name,
                )
        return None

    def _candidates_mlg_by_date(self, ins_date: datetime) -> List[Path]:
        """
        Glob for missionReport .mlg files whose filename date is within
        ±_MLG_DATE_WINDOW_DAYS of ins_date.

        Returns deduplicated list sorted by mtime descending (newest first).
        """
        seen: set = set()
        results: List[Path] = []
        for delta in range(-_MLG_DATE_WINDOW_DAYS, _MLG_DATE_WINDOW_DAYS + 1):
            date_str = (ins_date + timedelta(days=delta)).strftime("%Y-%m-%d")
            pattern = f"missionReport({date_str}_*.mlg"
            found = list(self._reports_dir.glob(pattern))
            if not found:
                found = list(self._reports_dir.rglob(pattern))
            for p in found:
                if p not in seen:
                    seen.add(p)
                    results.append(p)
        return sorted(results, key=lambda p: p.stat().st_mtime, reverse=True)

    def _ensure_txt(
        self, mlg_path: Path, mlg2txt_path: Optional[Path]
    ) -> Optional[Path]:
        """
        Return the .txt version of an .mlg file, converting via mlg2txt if needed.

        mlg2txt always writes <stem>[0].txt in the same directory as the .mlg.
        If the .txt already exists and is at least as new as the .mlg, it is
        returned directly without re-conversion.

        Returns None if conversion is unavailable or fails.
        """
        txt_path = mlg_path.parent / f"{mlg_path.stem}[0].txt"

        # Use existing .txt if it is up-to-date
        try:
            if txt_path.exists() and txt_path.stat().st_mtime >= mlg_path.stat().st_mtime:
                return txt_path
        except OSError:
            pass

        if mlg2txt_path is None:
            logger.debug(
                "mlg2txt not configured; cannot convert %s", mlg_path.name
            )
            # Return the .txt if it exists at all, even if stale
            return txt_path if txt_path.exists() else None

        if not mlg2txt_path.exists():
            logger.warning("mlg2txt not found at %s", mlg2txt_path)
            return txt_path if txt_path.exists() else None

        # Build the subprocess command
        if getattr(sys, 'frozen', False):
            cmd = [str(mlg2txt_path), '--output', str(mlg_path.parent), str(mlg_path)]
        else:
            cmd = [sys.executable, str(mlg2txt_path), '--output', str(mlg_path.parent), str(mlg_path)]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=(
                    subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                ),
            )
            if result.returncode != 0:
                logger.warning(
                    "mlg2txt failed for %s: %s", mlg_path.name, result.stderr.strip()
                )
                return None
        except Exception as exc:
            logger.warning("mlg2txt error for %s: %s", mlg_path.name, exc)
            return None

        return txt_path if txt_path.exists() else None

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
                    # GDate and GTime are space-separated tokens within the
                    # AType:0 record, e.g.:
                    #   T:0 AType:0 GDate:1941.9.27 GTime:7:24:34 MFile:...
                    for token in line.split():
                        if token.startswith("GDate:"):
                            gdate = token.split(":", 1)[1]
                        elif token.startswith("GTime:"):
                            gtime = token.split(":", 1)[1]
                    if gdate and gtime:
                        break
        except OSError as exc:
            logger.debug("Cannot read candidate %s: %s", path.name, exc)
            return None

        if not gdate or not gtime:
            return None

        # IL-2 omits leading zeros in GDate (e.g. "1941.9.7") and GTime
        # (e.g. "7:24:34").  Pad each component so strptime can match.
        date_parts = gdate.split(".")
        if len(date_parts) == 3:
            gdate = f"{date_parts[0]}.{date_parts[1].zfill(2)}.{date_parts[2].zfill(2)}"
        time_parts = gtime.split(":")
        if time_parts:
            time_parts[0] = time_parts[0].zfill(2)
            gtime = ":".join(time_parts)

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
            return True  # Cannot verify — accept the match

        last_t = self._read_last_t_value(path)
        if last_t is None:
            return True  # Cannot verify — accept the match

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
            - IL-2 dot-separated "YYYY.MM.DD HH:MM:SS"
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
