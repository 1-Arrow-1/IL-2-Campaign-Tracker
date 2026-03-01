"""
Diagnostic: print cp.db mission fields vs missionReport .txt headers
to trace why find_career_report() fails to link.

Usage:
    python tools/diagnose_career_linking.py <path_to_cp.db> <path_to_FlightLogs>

Example:
    python tools/diagnose_career_linking.py "C:/IL-2/data/Career/cp.db" "C:/IL-2/data/FlightLogs"
"""

import re
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path


def parse_datetime(raw):
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        try:
            return datetime.fromtimestamp(raw)
        except Exception as e:
            return f"TIMESTAMP_ERROR({e})"
    if isinstance(raw, str):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S",
                    "%Y-%m-%d", "%Y.%m.%d %H:%M:%S"):
            try:
                return datetime.strptime(raw, fmt)
            except ValueError:
                continue
    return f"UNPARSEABLE({raw!r})"


def parse_report_header(path):
    gdate = gtime = None
    try:
        with open(path, encoding='utf-8', errors='replace') as fh:
            for line in fh:
                s = line.strip()
                if s.startswith("GDate:"):
                    gdate = s.split(":", 1)[1].strip()
                elif s.startswith("GTime:"):
                    gtime = s.split(":", 1)[1].strip()
                if gdate and gtime:
                    break
    except OSError as e:
        return None, f"READ_ERROR({e})"

    if not gdate or not gtime:
        return None, f"MISSING(GDate={gdate!r}, GTime={gtime!r})"

    raw = f"{gdate} {gtime}"

    # Normalise (pad leading zeros)
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
            return datetime.strptime(combined, fmt), f"OK(raw={raw!r} → normalised={combined!r})"
        except ValueError:
            continue
    return None, f"PARSE_FAILED(normalised={combined!r})"


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    db_path = Path(sys.argv[1])
    logs_dir = Path(sys.argv[2])

    print(f"cp.db:     {db_path}")
    print(f"FlightLogs:{logs_dir}")
    print()

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Get first 5 missions
    rows = conn.execute(
        "SELECT id, careerId, insDate, startTime, endTime FROM mission ORDER BY startTime ASC LIMIT 10"
    ).fetchall()

    for row in rows:
        mid = row["id"]
        ins_date = row["insDate"]
        start_time = row["startTime"]

        ins_dt = parse_datetime(ins_date)
        start_dt = parse_datetime(start_time)

        print(f"─── Mission id={mid} ───────────────────────────────────")
        print(f"  insDate   raw={ins_date!r:30s}  parsed={ins_dt}")
        print(f"  startTime raw={start_time!r:30s}  parsed={start_dt}")

        if not isinstance(ins_dt, datetime):
            print(f"  !! insDate cannot be parsed as datetime — skipping file search")
            print()
            continue

        # Search for .mlg candidates
        candidates = []
        for delta in range(-1, 2):
            date_str = (ins_dt + timedelta(days=delta)).strftime("%Y-%m-%d")
            pattern = f"missionReport({date_str}_*.mlg"
            found = list(logs_dir.glob(pattern))
            if not found:
                found = list(logs_dir.rglob(pattern))
            candidates.extend(found)
        candidates = sorted(set(candidates), key=lambda p: p.stat().st_mtime, reverse=True)

        if not candidates:
            print(f"  !! No .mlg files found for date window around {ins_dt.date()}")
            # Show what .mlg files DO exist
            all_mlg = sorted(logs_dir.rglob("missionReport(*.mlg"))
            if all_mlg:
                print(f"     Existing .mlg files ({len(all_mlg)} total):")
                for p in all_mlg[:5]:
                    print(f"       {p.name}")
                if len(all_mlg) > 5:
                    print(f"       ... and {len(all_mlg)-5} more")
            else:
                print(f"     No .mlg files at all in {logs_dir}")
            print()
            continue

        print(f"  .mlg candidates ({len(candidates)}):")
        for mlg in candidates:
            txt_path = mlg.parent / f"{mlg.stem}[0].txt"
            if txt_path.exists():
                report_dt, status = parse_report_header(txt_path)
                match = "✓ MATCH" if report_dt == start_dt else "✗ NO MATCH"
                print(f"    {mlg.name}")
                print(f"      .txt exists: {txt_path.name}")
                print(f"      header: {status}")
                print(f"      report_start={report_dt}  startTime={start_dt}  → {match}")
            else:
                print(f"    {mlg.name}  (no .txt yet)")
        print()

    conn.close()


if __name__ == "__main__":
    main()
