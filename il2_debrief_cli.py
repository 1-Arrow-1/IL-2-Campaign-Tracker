"""
il2_debrief_cli.py
------------------
Headless command-line front end to the IL-2 mission debrief parser, for use
by other programs (e.g. PWCG+). See docs/integration/DEBRIEF_CLI.md.

Usage:
    il2_debrief <log> [<log> ...] [--out PATH] [--mlg2txt PATH] [--pretty] [--verbose]

<log> is either ONE .mlg file, or the .txt part(s) of ONE mission
(missionReport(...)[0].txt, [1].txt, ...), which are merged in index order.

Contract:
    stdout  exactly one line of JSON: {"ok": true, "output": ..., "schema_version": ...}
            or {"ok": false, "error_code": ..., "error": ...}
    stderr  diagnostics only
    exit    0 ok | 2 bad input | 3 .mlg conversion failed | 4 parse failed | 5 no player in log
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from utils.logging import SafeStreamHandler
from utils.pathing import get_base_path

# Bump when the output JSON changes in a way a consumer could notice
# (renamed/removed fields, changed meaning). Adding new fields does not bump it.
SCHEMA_VERSION = 1
# Bump whenever the analyser's results change for the same log (docs/integration/DEBRIEF_CLI.md §7).
ANALYSER_REVISION = 2

EXIT_OK = 0
EXIT_BAD_INPUT = 2
EXIT_MLG_FAILED = 3
EXIT_PARSE_FAILED = 4
EXIT_NO_PLAYER = 5

_PART_INDEX_RE = re.compile(r"\[(\d+)\]\.txt$", re.IGNORECASE)
# The game prefixes some AI pilot names with a control character (e.g. "\x01Sergei Mosolov").
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")


class CliError(Exception):
    def __init__(self, exit_code: int, error_code: str, message: str):
        super().__init__(message)
        self.exit_code = exit_code
        self.error_code = error_code


def _tracker_version() -> str:
    candidates = [get_base_path(__file__) / "version.txt"]
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys._MEIPASS) / "version.txt")
    for path in candidates:
        try:
            return path.read_text(encoding="utf-8").strip() or "unknown"
        except OSError:
            continue
    return "unknown"


def _route_parser_logging_to_stderr(verbose: bool) -> None:
    """The parser logs to stdout by default; stdout is reserved for the status line."""
    import il2_mission_debrief

    handler = SafeStreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    parser_logger = il2_mission_debrief.logger
    parser_logger.handlers.clear()
    parser_logger.addHandler(handler)
    parser_logger.setLevel(logging.INFO if verbose else logging.WARNING)


def _find_mlg2txt(explicit: str | None) -> list[str]:
    """Return the command prefix used to run mlg2txt."""
    if explicit:
        path = Path(explicit)
        if not path.exists():
            raise CliError(EXIT_BAD_INPUT, "mlg2txt_not_found", f"mlg2txt not found: {path}")
        return [sys.executable, str(path)] if path.suffix.lower() == ".py" else [str(path)]
    base = get_base_path(__file__)
    exe = base / "mlg2txt.exe"
    if exe.exists():
        return [str(exe)]
    script = base / "mlg2txt.py"
    if script.exists() and not getattr(sys, "frozen", False):
        return [sys.executable, str(script)]
    raise CliError(
        EXIT_MLG_FAILED,
        "mlg2txt_not_found",
        "Cannot convert .mlg: mlg2txt.exe not found next to this program (use --mlg2txt)",
    )


def _convert_mlg(mlg_path: Path, workdir: Path, mlg2txt: str | None) -> Path:
    cmd = _find_mlg2txt(mlg2txt) + ["--output", str(workdir), str(mlg_path)]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CliError(EXIT_MLG_FAILED, "mlg_conversion_failed", f"mlg2txt failed: {exc}") from exc
    produced = sorted(workdir.glob("*.txt"))
    if result.returncode != 0 or not produced:
        detail = (result.stderr or result.stdout or "").strip()[-500:]
        raise CliError(EXIT_MLG_FAILED, "mlg_conversion_failed", f"mlg2txt failed: {detail}")
    return produced[0]


def _merge_txt_parts(parts: list[Path], workdir: Path) -> Path:
    """Concatenate the game's split log files in [N] index order."""
    def index(p: Path) -> int:
        m = _PART_INDEX_RE.search(p.name)
        return int(m.group(1)) if m else 0

    ordered = sorted(parts, key=index)
    merged = workdir / "merged_missionReport.txt"
    with open(merged, "w", encoding="utf-8") as out:
        for part in ordered:
            text = part.read_text(encoding="utf-8", errors="replace")
            out.write(text)
            if text and not text.endswith("\n"):
                out.write("\n")
    return merged


def _default_out_path(first_input: Path) -> Path:
    stem = re.sub(r"\[\d+\]$", "", first_input.stem)
    return first_input.with_name(f"{stem}.events.json")


def run(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="il2_debrief",
        description="Analyse an IL-2 Great Battles mission log and write the facts as JSON.",
    )
    ap.add_argument("logs", nargs="+", help="one .mlg file, or the .txt part(s) of one mission")
    ap.add_argument("--out", help="output JSON path (default: <log>.events.json next to the log)")
    ap.add_argument("--mlg2txt", help="path to mlg2txt.exe (default: next to this program)")
    ap.add_argument("--pretty", action="store_true", help="indent the output JSON")
    ap.add_argument("--verbose", action="store_true", help="write parser diagnostics to stderr")
    args = ap.parse_args(argv)

    try:
        inputs = [Path(p) for p in args.logs]
        missing = [str(p) for p in inputs if not p.is_file()]
        if missing:
            raise CliError(EXIT_BAD_INPUT, "input_not_found", f"Input not found: {', '.join(missing)}")
        suffixes = {p.suffix.lower() for p in inputs}
        if suffixes == {".mlg"}:
            if len(inputs) != 1:
                raise CliError(EXIT_BAD_INPUT, "bad_input", "Pass exactly one .mlg file per call")
        elif suffixes != {".txt"}:
            raise CliError(EXIT_BAD_INPUT, "bad_input", "Inputs must be one .mlg file or .txt log parts")

        out_path = Path(args.out) if args.out else _default_out_path(inputs[0])
        _route_parser_logging_to_stderr(args.verbose)
        import il2_mission_debrief

        with tempfile.TemporaryDirectory(prefix="il2_debrief_") as tmp:
            workdir = Path(tmp)
            if suffixes == {".mlg"}:
                log_path = _convert_mlg(inputs[0], workdir, args.mlg2txt)
            elif len(inputs) == 1:
                log_path = inputs[0]
            else:
                log_path = _merge_txt_parts(inputs, workdir)

            raw_json = workdir / "parser_output.json"
            try:
                parser = il2_mission_debrief.MissionDebriefParser(log_path, verbose=args.verbose)
                stats = parser.parse()
                if stats.player_id is None and stats.player_plid is None:
                    raise CliError(
                        EXIT_NO_PLAYER,
                        "no_player",
                        "No player aircraft (ISPL:1) found in the log",
                    )
                parser.to_json(raw_json)
                data = json.loads(raw_json.read_text(encoding="utf-8"))
            except CliError:
                raise
            except Exception as exc:
                raise CliError(EXIT_PARSE_FAILED, "parse_failed", f"Parse failed: {exc}") from exc

        for flight in data.get("squadron_flights") or []:
            if isinstance(flight.get("name"), str):
                flight["name"] = _CONTROL_CHARS_RE.sub("", flight["name"]).strip()

        output = {
            "schema_version": SCHEMA_VERSION,
            "generator": {
                "name": "IL-2 Campaign Tracker debrief",
                "version": _tracker_version(),
                "revision": ANALYSER_REVISION,
            },
            "source_files": [p.name for p in inputs],
            **data,
        }
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_out = out_path.with_name(out_path.name + ".tmp")
        tmp_out.write_text(
            json.dumps(output, indent=2 if args.pretty else None, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(tmp_out, out_path)  # atomic: consumers never see a half-written file

        print(json.dumps({
            "ok": True,
            "output": str(out_path.resolve()),
            "schema_version": SCHEMA_VERSION,
        }))
        return EXIT_OK

    except CliError as err:
        print(json.dumps({"ok": False, "error_code": err.error_code, "error": str(err)}))
        return err.exit_code


if __name__ == "__main__":
    sys.exit(run())
