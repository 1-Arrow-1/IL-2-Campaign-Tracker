"""
Duplicate an NPC pilot into a new career/theatre and carry forward awards.

This script is intended for squad pilots in IL-2 Career Mode cp.db where:
- a new theatre uses a new career.id
- the squad roster uses a new pilot row for the same NPC
- prior awards must be copied into the new career to prevent re-awarding

Usage:
    python tools/duplicate_career_pilot.py ^
        --db "C:/.../data/Career/cp.db" ^
        --source-pilot-id 2392 ^
        --target-career-id 79 ^
        --target-squadron-id 95

    python tools/duplicate_career_pilot.py ^
        --db "C:/.../data/Career/cp.db" ^
        --source-pilot-id 2392 ^
        --target-pilot-id 2432 ^
        --target-career-id 79 ^
        --target-squadron-id 95

Optional:
    --lookup-name "Berthold Lueders"  Find matching pilot/career/squadron ids
    --source-career-id 78          Explicit source award snapshot career
    --target-pilot-id 2432         Reuse existing copied pilot instead of creating one
    --name "Berthold Lueders"      Validation only
    --backup                       Create cp.db backup before writing
    --dry-run                      Print intended actions without writing
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Duplicate a squad pilot for a new career and copy awards."
    )
    parser.add_argument("--db", required=True, help="Path to IL-2 Career cp.db")
    parser.add_argument(
        "--lookup-name",
        help="Lookup mode: print matching pilot, career, and squadron IDs for a full pilot name",
    )
    parser.add_argument(
        "--source-pilot-id",
        type=int,
        help="Existing pilot.id to duplicate from the previous theatre",
    )
    parser.add_argument(
        "--target-career-id",
        type=int,
        help="New career.id that should receive the duplicated pilot and awards",
    )
    parser.add_argument(
        "--target-squadron-id",
        type=int,
        help="squadron.id for the pilot in the new theatre",
    )
    parser.add_argument(
        "--target-pilot-id",
        type=int,
        help="Existing pilot.id to reuse in the target career instead of creating a duplicate",
    )
    parser.add_argument(
        "--source-career-id",
        type=int,
        help="Source career.id to copy awards from. Defaults to latest award snapshot for the source pilot.",
    )
    parser.add_argument(
        "--name",
        help="Optional expected full pilot name used as a safety check",
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Create a timestamped cp.db backup before modifying anything",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned changes without writing to the database",
    )
    args = parser.parse_args()
    if not args.lookup_name:
        missing = [
            flag
            for flag, value in (
                ("--source-pilot-id", args.source_pilot_id),
                ("--target-career-id", args.target_career_id),
                ("--target-squadron-id", args.target_squadron_id),
            )
            if value is None
        ]
        if missing:
            parser.error(f"the following arguments are required unless --lookup-name is used: {' '.join(missing)}")
    return args


def connect_rw(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def backup_database(db_path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.with_name(f"{db_path.name}.bak_{stamp}")
    shutil.copy2(db_path, backup_path)
    return backup_path


def fetch_one(conn: sqlite3.Connection, sql: str, params: Iterable) -> sqlite3.Row:
    row = conn.execute(sql, tuple(params)).fetchone()
    if row is None:
        raise SystemExit(f"Query returned no rows: {sql}")
    return row


def resolve_source_career_id(conn: sqlite3.Connection, source_pilot_id: int) -> int:
    row = conn.execute(
        """
        SELECT careerId
        FROM award
        WHERE pilotId = ?
        ORDER BY date DESC, id DESC
        LIMIT 1
        """,
        (source_pilot_id,),
    ).fetchone()
    if row is None:
        raise SystemExit(
            f"Could not infer source career from award rows for pilotId={source_pilot_id}"
        )
    return int(row["careerId"])


def duplicate_pilot_row(
    conn: sqlite3.Connection,
    source_pilot_id: int,
    target_squadron_id: int,
) -> sqlite3.Row:
    source_row = fetch_one(
        conn,
        "SELECT * FROM pilot WHERE id = ? AND isDeleted = 0",
        (source_pilot_id,),
    )

    columns = [col[1] for col in conn.execute("PRAGMA table_info(pilot)").fetchall()]
    insert_cols = [c for c in columns if c != "id"]
    values = [source_row[c] for c in insert_cols]

    overrides = {
        "squadronId": target_squadron_id,
        "insDate": datetime.now().strftime("%Y.%m.%d %H:%M:%S"),
        "isDeleted": 0,
    }

    for key, value in overrides.items():
        if key in insert_cols:
            values[insert_cols.index(key)] = value

    placeholders = ", ".join("?" for _ in insert_cols)
    col_list = ", ".join(insert_cols)
    conn.execute(
        f"INSERT INTO pilot ({col_list}) VALUES ({placeholders})",
        values,
    )
    new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    return fetch_one(conn, "SELECT * FROM pilot WHERE id = ?", (new_id,))


def prepare_existing_target_pilot(
    conn: sqlite3.Connection,
    target_pilot_id: int,
    target_squadron_id: int,
) -> sqlite3.Row:
    target_row = fetch_one(
        conn,
        "SELECT * FROM pilot WHERE id = ? AND isDeleted = 0",
        (target_pilot_id,),
    )
    conn.execute(
        """
        UPDATE pilot
        SET squadronId = ?, insDate = ?, isDeleted = 0
        WHERE id = ?
        """,
        (
            target_squadron_id,
            datetime.now().strftime("%Y.%m.%d %H:%M:%S"),
            target_pilot_id,
        ),
    )
    return fetch_one(conn, "SELECT * FROM pilot WHERE id = ?", (target_pilot_id,))


def replace_awards(
    conn: sqlite3.Connection,
    source_career_id: int,
    source_pilot_id: int,
    target_career_id: int,
    target_pilot_row: sqlite3.Row,
    target_squad_config_id: int,
) -> int:
    conn.execute(
        "DELETE FROM award WHERE careerId = ? AND pilotId = ?",
        (target_career_id, int(target_pilot_row["id"])),
    )

    award_rows = conn.execute(
        """
        SELECT type, date, pilotName, pilotRank, squadName, isDeleted, PersonageId,
               x, y, CausedByType, CausedById, Show, GameTime, PersonageAwardId
        FROM award
        WHERE careerId = ? AND pilotId = ?
        ORDER BY date, id
        """,
        (source_career_id, source_pilot_id),
    ).fetchall()

    if not award_rows:
        return 0

    for row in award_rows:
        conn.execute(
            """
            INSERT INTO award (
                careerId, type, date, pilotId, pilotName, pilotRank, squadName,
                insDate, isDeleted, PersonageId, x, y, CausedByType, CausedById,
                Show, SquadId, squadConfigId, GameTime, PersonageAwardId
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                target_career_id,
                row["type"],
                row["date"],
                int(target_pilot_row["id"]),
                row["pilotName"],
                row["pilotRank"],
                row["squadName"],
                datetime.now().strftime("%Y.%m.%d %H:%M:%S"),
                row["isDeleted"],
                row["PersonageId"],
                row["x"],
                row["y"],
                row["CausedByType"],
                row["CausedById"],
                row["Show"],
                int(target_pilot_row["squadronId"]),
                target_squad_config_id,
                row["GameTime"],
                row["PersonageAwardId"],
            ),
        )

    return len(award_rows)


def lookup_name(conn: sqlite3.Connection, full_name: str) -> dict:
    parts = full_name.strip().split(None, 1)
    if len(parts) != 2:
        raise SystemExit("--lookup-name requires 'First Last'")
    first_name, last_name = parts

    pilot_rows = conn.execute(
        """
        SELECT p.id, p.name, p.lastName, p.squadronId, p.rankId, p.score, p.sorties,
               p.careerStartDate, p.stateDate, p.insDate, p.isDeleted,
               s.configId AS squadronConfigId
        FROM pilot p
        LEFT JOIN squadron s ON s.id = p.squadronId
        WHERE lower(p.name) = lower(?) AND lower(p.lastName) = lower(?)
        ORDER BY p.id
        """,
        (first_name, last_name),
    ).fetchall()

    pilot_ids = [int(row["id"]) for row in pilot_rows]
    career_rows = []
    if pilot_ids:
        placeholders = ", ".join("?" for _ in pilot_ids)
        career_rows = conn.execute(
            f"""
            SELECT id, personageId, playerId, tvd, startDate, currentDate,
                   squadronId, extends, isDeleted, infoId, phaseId
            FROM career
            WHERE playerId IN ({placeholders})
            ORDER BY id
            """,
            pilot_ids,
        ).fetchall()

    award_snapshot_rows = []
    for pilot_id in pilot_ids:
        row = conn.execute(
            """
            SELECT pilotId, careerId, date, type, pilotRank, isDeleted
            FROM award
            WHERE pilotId = ?
            ORDER BY date DESC, id DESC
            LIMIT 1
            """,
            (pilot_id,),
        ).fetchone()
        if row is not None:
            award_snapshot_rows.append(row)

    return {
        "lookup_name": full_name,
        "pilots": [dict(row) for row in pilot_rows],
        "careers": [dict(row) for row in career_rows],
        "latest_award_snapshots": [dict(row) for row in award_snapshot_rows],
    }


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"cp.db not found: {db_path}")

    conn = connect_rw(db_path)
    try:
        if args.lookup_name:
            print(lookup_name(conn, args.lookup_name))
            return 0

        source_pilot = fetch_one(
            conn,
            "SELECT * FROM pilot WHERE id = ?",
            (args.source_pilot_id,),
        )
        target_career = fetch_one(
            conn,
            "SELECT * FROM career WHERE id = ? AND isDeleted = 0",
            (args.target_career_id,),
        )
        target_squadron = fetch_one(
            conn,
            "SELECT * FROM squadron WHERE id = ?",
            (args.target_squadron_id,),
        )

        full_name = f"{source_pilot['name']} {source_pilot['lastName']}".strip()
        if args.name and full_name.lower() != args.name.strip().lower():
            raise SystemExit(
                f"Pilot name mismatch: source row is '{full_name}', expected '{args.name}'"
            )

        source_career_id = args.source_career_id or resolve_source_career_id(
            conn, args.source_pilot_id
        )

        source_award_count = conn.execute(
            "SELECT COUNT(*) FROM award WHERE careerId = ? AND pilotId = ?",
            (source_career_id, args.source_pilot_id),
        ).fetchone()[0]

        if args.dry_run:
            print(
                {
                    "db": str(db_path),
                    "source_pilot_id": args.source_pilot_id,
                    "target_pilot_id": args.target_pilot_id,
                    "source_pilot_name": full_name,
                    "source_career_id": source_career_id,
                    "target_career_id": args.target_career_id,
                    "target_squadron_id": args.target_squadron_id,
                    "target_squadron_config_id": target_squadron["configId"],
                    "source_award_count": source_award_count,
                    "mode": "reuse-existing-target-pilot" if args.target_pilot_id else "duplicate-source-pilot",
                }
            )
            return 0

        backup_path: Optional[Path] = None
        if args.backup:
            backup_path = backup_database(db_path)

        with conn:
            if args.target_pilot_id:
                new_pilot = prepare_existing_target_pilot(
                    conn,
                    target_pilot_id=args.target_pilot_id,
                    target_squadron_id=args.target_squadron_id,
                )
            else:
                new_pilot = duplicate_pilot_row(
                    conn,
                    source_pilot_id=args.source_pilot_id,
                    target_squadron_id=args.target_squadron_id,
                )
            copied_awards = replace_awards(
                conn,
                source_career_id=source_career_id,
                source_pilot_id=args.source_pilot_id,
                target_career_id=args.target_career_id,
                target_pilot_row=new_pilot,
                target_squad_config_id=int(target_squadron["configId"]),
            )

        print(
            {
                "backup": str(backup_path) if backup_path else None,
                "source_pilot_id": args.source_pilot_id,
                "target_pilot_id": int(new_pilot["id"]),
                "pilot_name": full_name,
                "mode": "reused-existing-target-pilot" if args.target_pilot_id else "duplicated-source-pilot",
                "source_career_id": source_career_id,
                "target_career_id": int(target_career["id"]),
                "target_squadron_id": int(new_pilot["squadronId"]),
                "target_squadron_config_id": int(target_squadron["configId"]),
                "copied_awards": copied_awards,
            }
        )
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
