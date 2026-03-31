"""
career_pdf_report.py

Generates a PDF "Career Service Record" report containing:
 - Per-day chapters: per-mission kills table (campaign style) + mission stats
   table (Duration / A/C Damage / Pilot Damage / Result) + other incidences,
   awards/promotions with full-size images, and AI story text.
 - Final pages: career-wide summary statistics.

Requires: reportlab >= 4.0  (pip install reportlab)
"""

from __future__ import annotations

import io
import logging
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------
_C_DARK    = "#1a2035"   # Navy – major headers / table header bg
_C_ACCENT  = "#b8962e"   # Muted gold – accent bars / chapter strip
_C_MID     = "#4a5568"   # Slate – section sub-headers / footer
_C_ROW_ALT = "#f7f7f9"   # Very light – table alternate row
_C_HR      = "#c0c0c0"   # Rule colour
_C_WHITE   = "#ffffff"


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------
def _safe(text: Any, fallback: str = "") -> str:
    """Stringify + replace non-Latin-1 chars so built-in Helvetica renders them."""
    if text is None:
        return fallback
    return "".join(c if ord(c) < 256 else "?" for c in str(text))


def _pct(value: Any) -> str:
    try:
        return f"{float(value):.0f}%"
    except (TypeError, ValueError):
        return "—"


def _award_display_name(name_key: str) -> str:
    """Resolve an award name_key (e.g. 'fighters_bronze') to a human-readable
    display name via the locale dictionary (progression.awards.<key>).
    Falls back to title-casing the key when the locale lookup misses.
    """
    if not name_key:
        return ""
    try:
        from utils.i18n import t
        result = t(f"progression.awards.{name_key}")
        if not result.startswith("["):
            return result
    except Exception:
        pass
    return name_key.replace("_", " ").replace("-", " ").title()


# ---------------------------------------------------------------------------
# Kill event parser (used only as fallback when sortie_stats are absent)
# ---------------------------------------------------------------------------
def _extract_kills(mission_json: dict) -> list[tuple[str, str, int]]:
    """Parse events array → sorted list of (category, target, count).

    Category values: "Air", "Ground", "Naval", "Building".
    Events with type "Kill" are counted; duplicates by (category, target) aggregated.
    """
    events = mission_json.get("events", []) if isinstance(mission_json, dict) else []
    kills: dict[tuple[str, str], int] = {}
    for ev in (events or []):
        if not isinstance(ev, dict):
            continue
        if (ev.get("type") or "").lower() != "kill":
            continue
        target   = _safe(ev.get("target") or "Unknown target")
        category = _safe(ev.get("category") or "Air")
        kills[(category, target)] = kills.get((category, target), 0) + 1

    _order = {"Air": 0, "Ground": 1, "Naval": 2, "Building": 3}
    return sorted(
        [(cat, tgt, cnt) for (cat, tgt), cnt in kills.items()],
        key=lambda x: (_order.get(x[0], 99), -x[2], x[1]),
    )


# ---------------------------------------------------------------------------
# Image resolution
# ---------------------------------------------------------------------------
def _load_image_bytes(
    image_url: Optional[str],
    data_dir: Optional[Path],
    game_dir: Optional[Path],
) -> Optional[bytes]:
    """Convert a /api/career_assets/... URL to raw PNG/bytes.
    Returns None when the file cannot be found.
    """
    if not image_url:
        return None
    prefix = "/api/career_assets/"
    if not image_url.startswith(prefix):
        return None
    asset_path = image_url[len(prefix):]

    roots: list[Path] = []
    if data_dir:
        roots.append(data_dir)
    if game_dir:
        roots.append(game_dir / "data" / "swf")

    for root in roots:
        full = (root / asset_path).resolve()
        try:
            from campaign_service_record.utils.image_utils import (
                convert_dds_to_png_bytes,
                find_existing_image_path,
            )
            existing = find_existing_image_path(full)
            if not existing:
                continue
            if existing.suffix.lower() == ".dds":
                raw = convert_dds_to_png_bytes(existing)
                return raw if raw else None
            return existing.read_bytes()
        except Exception:
            pass
    return None


# ---------------------------------------------------------------------------
# Category icon loader
# ---------------------------------------------------------------------------
_ICON_MAP: dict[str, str] = {
    "Aircraft":  "icon_aircraft.png",
    "Vehicles":  "icon_vehicles.png",
    "Railroad":  "icon_railroad.png",
    "Armaments": "icon_armaments.png",
    "Buildings": "icon_buildings.png",
    "Marine":    "icon_marine.png",
}


def _load_icon_bytes(
    cat_name: str,
    data_dir: Optional[Path],
    game_dir: Optional[Path],
) -> Optional[bytes]:
    """Load a combat-results category icon PNG from game assets.

    Search order:
        1. <game_dir>/data/swf/CampaignRanksAwards/Misc/<filename>
        2. <data_dir>/CampaignRanksAwards/Misc/<filename>
    """
    filename = _ICON_MAP.get(cat_name, "")
    if not filename:
        return None
    candidates: list[Path] = []
    if game_dir:
        candidates.append(game_dir / "data" / "swf" / "CampaignRanksAwards" / "Misc" / filename)
    if data_dir:
        candidates.append(data_dir / "CampaignRanksAwards" / "Misc" / filename)
    for path in candidates:
        try:
            if path.exists():
                return path.read_bytes()
        except Exception:
            pass
    return None


# ---------------------------------------------------------------------------
# Per-day helpers
# ---------------------------------------------------------------------------
def _events_for_date(events: list[dict], date: str) -> list[dict]:
    return [e for e in events if e.get("date") == date]


def _incidences_for_date(other_incidences: list[dict], date: str) -> list[dict]:
    return [oi for oi in other_incidences if oi.get("sort_key") == date]


def _format_incidence(oi: dict) -> str:
    oi_type = oi.get("type", "")
    if oi_type == "RECOVERY":
        start = oi.get("start_date", "?")
        end   = oi.get("end_date", "?")
        days  = oi.get("duration_days", "?")
        return f"Medical Leave / Recovery: {start} to {end} ({days} days)"
    if oi_type == "COMMAND":
        return "Appointed Squadron Commander"
    if oi_type == "DEPUTY_COMMAND":
        return "Appointed Deputy Squadron Commander"
    if oi_type == "SQUADRON_CHANGE":
        old = oi.get("old_squadron", "?")
        new = oi.get("new_squadron", "?")
        return f"Squadron Transfer: {old} \u2192 {new}"
    return str(oi_type).replace("_", " ").title()


# ---------------------------------------------------------------------------
# PDF flowable builder
# ---------------------------------------------------------------------------
def _build_story(
    career_detail: dict,
    day_contexts: list[dict],
    story_chapters: list[dict],
    data_dir: Optional[Path],
    game_dir: Optional[Path],
) -> list:
    """Return the list of reportlab Flowables that make up the PDF."""

    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        HRFlowable, Image, KeepTogether, Paragraph,
        Spacer, Table, TableStyle,
    )

    PAGE_W, PAGE_H = A4
    MARGIN  = 20 * mm
    CW      = PAGE_W - 2 * MARGIN      # usable content width
    IMG_SZ  = 54 * mm                  # award/rank image (+50% → 54 mm)

    base = getSampleStyleSheet()

    def S(name: str, **kw) -> ParagraphStyle:
        parent = kw.pop("parent", "Normal")
        return ParagraphStyle(name, parent=base[parent], **kw)

    sty = {
        "title":     S("R_Title",     parent="Heading1", fontSize=26,
                        alignment=TA_CENTER, spaceAfter=2,
                        textColor=colors.HexColor(_C_DARK)),
        "subtitle":  S("R_Sub",       fontSize=10,
                        alignment=TA_CENTER, spaceAfter=4,
                        textColor=colors.HexColor(_C_MID)),
        "ch_hdr":    S("R_ChHdr",     parent="Heading2", fontSize=13,
                        spaceBefore=14, spaceAfter=3,
                        textColor=colors.HexColor(_C_DARK)),
        "mis_hdr":   S("R_MisHdr",    fontSize=9, fontName="Helvetica-Bold",
                        spaceBefore=8, spaceAfter=2,
                        textColor=colors.HexColor(_C_MID)),
        "sec_hdr":   S("R_SecHdr",    parent="Heading3", fontSize=9,
                        spaceBefore=6, spaceAfter=2,
                        textColor=colors.HexColor(_C_MID)),
        "body":      S("R_Body",      fontSize=9, leading=13, spaceAfter=6,
                        alignment=TA_JUSTIFY),
        "story_ttl": S("R_StoryTtl",  fontSize=10, leading=13, spaceAfter=3,
                        textColor=colors.HexColor(_C_DARK),
                        fontName="Helvetica-Bold"),
        "caption":   S("R_Cap",       fontSize=8, leading=10,
                        textColor=colors.HexColor(_C_MID)),
        "smry_hdr":  S("R_SmryHdr",   parent="Heading1", fontSize=20,
                        alignment=TA_CENTER, spaceAfter=8,
                        textColor=colors.HexColor(_C_DARK)),
        "tbl_hdr":   S("R_TblHdr",    fontSize=8, fontName="Helvetica-Bold",
                        alignment=TA_CENTER, textColor=colors.white),
        "tbl_cell":  S("R_TblCell",   fontSize=8, alignment=TA_CENTER),
        "tbl_label": S("R_TblLabel",  fontSize=8, fontName="Helvetica-Bold"),
        "tbl_val":   S("R_TblVal",    fontSize=8),
        "award_txt": S("R_AwardTxt",  fontSize=9, leading=12),
        "no_kills":  S("R_NoKills",   fontSize=8, textColor=colors.HexColor(_C_MID),
                        spaceBefore=2, spaceAfter=4),
        # Combat results block (icon-style)
        "cr_count":  S("R_CrCount",   fontSize=18, fontName="Helvetica-Bold",
                        alignment=TA_CENTER, textColor=colors.HexColor(_C_DARK),
                        spaceAfter=0, spaceBefore=0),
        "cr_cat":    S("R_CrCat",     fontSize=7,  fontName="Helvetica-Bold",
                        alignment=TA_CENTER, textColor=colors.HexColor(_C_MID),
                        spaceAfter=0, spaceBefore=0),
        "cr_sub_n":  S("R_CrSubN",    fontSize=7,  fontName="Helvetica",
                        alignment=TA_LEFT,   textColor=colors.HexColor(_C_DARK)),
        "cr_sub_v":  S("R_CrSubV",    fontSize=7,  fontName="Helvetica-Bold",
                        alignment=TA_RIGHT,  textColor=colors.HexColor(_C_DARK)),
    }

    # -----------------------------------------------------------------------
    # Style builders
    # -----------------------------------------------------------------------
    def _tbl_style(header_rows: int = 1) -> TableStyle:
        return TableStyle([
            ("BACKGROUND",     (0, 0), (-1, header_rows - 1),
             colors.HexColor(_C_DARK)),
            ("TEXTCOLOR",      (0, 0), (-1, header_rows - 1),
             colors.white),
            ("FONTNAME",       (0, 0), (-1, header_rows - 1),
             "Helvetica-Bold"),
            ("FONTSIZE",       (0, 0), (-1, -1), 8),
            ("ALIGN",          (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, header_rows), (-1, -1),
             [colors.white, colors.HexColor(_C_ROW_ALT)]),
            ("GRID",           (0, 0), (-1, -1), 0.3,
             colors.HexColor(_C_HR)),
            ("TOPPADDING",     (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING",  (0, 0), (-1, -1), 3),
            ("LEFTPADDING",    (0, 0), (-1, -1), 4),
            ("RIGHTPADDING",   (0, 0), (-1, -1), 4),
        ])

    def _bold_last_row(style: TableStyle, row_idx: int) -> TableStyle:
        """Append commands to bold the given row (used for totals)."""
        style.add("FONTNAME",   (0, row_idx), (-1, row_idx), "Helvetica-Bold")
        style.add("BACKGROUND", (0, row_idx), (-1, row_idx),
                  colors.HexColor(_C_ROW_ALT))
        style.add("LINEABOVE",  (0, row_idx), (-1, row_idx), 0.6,
                  colors.HexColor(_C_HR))
        return style

    def _kv_table(rows: list[tuple[str, str]]) -> Table:
        data = [
            [Paragraph(_safe(k), sty["tbl_label"]),
             Paragraph(_safe(v), sty["tbl_val"])]
            for k, v in rows
        ]
        t = Table(data, colWidths=[CW * 0.42, CW * 0.58])
        t.setStyle(TableStyle([
            ("FONTSIZE",       (0, 0), (-1, -1), 8),
            ("VALIGN",         (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1),
             [colors.white, colors.HexColor(_C_ROW_ALT)]),
            ("GRID",           (0, 0), (-1, -1), 0.3,
             colors.HexColor(_C_HR)),
            ("TOPPADDING",     (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING",  (0, 0), (-1, -1), 3),
            ("LEFTPADDING",    (0, 0), (-1, -1), 5),
            ("RIGHTPADDING",   (0, 0), (-1, -1), 5),
        ]))
        return t

    def _keep(flowables: list) -> KeepTogether:
        """Wrap in KeepTogether — moves to next page if it doesn't fit.
        Falls back to splitting only when the group is taller than a full page.
        """
        return KeepTogether(flowables)

    def hr() -> HRFlowable:
        return HRFlowable(
            width="100%", thickness=0.5,
            color=colors.HexColor(_C_HR),
            spaceAfter=3, spaceBefore=3,
        )

    def accent_bar() -> HRFlowable:
        return HRFlowable(
            width="100%", thickness=2,
            color=colors.HexColor(_C_ACCENT),
            spaceAfter=6, spaceBefore=2,
        )

    def img_flowable(img_bytes: Optional[bytes]) -> Optional[Image]:
        if not img_bytes:
            return None
        try:
            return Image(io.BytesIO(img_bytes), width=IMG_SZ, height=IMG_SZ)
        except Exception:
            return None

    # -----------------------------------------------------------------------
    # Combat results block — icon style matching campaign PDF / in-game layout
    # Primary source: cp.db sortie_stats (all 6 categories)
    # Optional:       mission report events (per-aircraft-type in Aircraft col)
    # -----------------------------------------------------------------------
    def _combat_results_flowables(
        sortie_stats: dict,
        mission_json: dict,
    ) -> list:
        """Return [header_table, subcat_table] flowables for the combat results
        block, styled to match the campaign PDF / in-game screenshot.

        Returns an empty list when all categories have zero kills.
        """
        from utils.combat_results import KILL_MAPPING

        stats = sortie_stats if isinstance(sortie_stats, dict) else {}
        cats  = list(KILL_MAPPING.keys())
        n     = len(cats)   # always 6
        cat_w = CW / n

        # --- Aggregate from cp.db stats (all categories) ---
        cat_totals: dict[str, int] = {}
        cat_sub: dict[str, list[tuple[str, int]]] = {}
        for cat, subcats in KILL_MAPPING.items():
            total = 0
            sub_rows: list[tuple[str, int]] = []
            for subcat, key in subcats.items():
                cnt = int(stats.get(key, 0) or 0)
                sub_rows.append((subcat, cnt))
                total += cnt
            cat_totals[cat] = total
            cat_sub[cat] = sub_rows

        if sum(cat_totals.values()) == 0:
            return []

        # Aircraft column always uses cp.db subcategories (Light/Medium/Heavy/Parked/Balloons)
        # — no per-aircraft-type override from mission reports here.

        # --- Icon cells (top row) ---
        ICON_SZ = 9 * mm

        def _icon_cell(cat_name: str):
            raw = _load_icon_bytes(cat_name, data_dir, game_dir)
            if raw:
                try:
                    return Image(io.BytesIO(raw), width=ICON_SZ, height=ICON_SZ)
                except Exception:
                    pass
            return Paragraph("", sty["cr_cat"])

        # --- Header table: 2 rows × 6 cols ---
        # Row 0: icons
        # Row 1: count (large bold) + category name stacked in one cell — ensures
        #         both are truly centred vertically and horizontally together.
        icon_row = [_icon_cell(cat) for cat in cats]
        count_name_row = [
            Paragraph(
                f'<font size="18"><b>{cat_totals[cat]}</b></font>'
                f'<br/>'
                f'<font size="7">{_safe(cat).upper()}</font>',
                sty["cr_count"],   # base: CENTER, Helvetica-Bold
            )
            for cat in cats
        ]

        hdr_tbl = Table(
            [icon_row, count_name_row],
            colWidths=[cat_w] * n,
            rowHeights=[ICON_SZ + 4 * mm, 14 * mm],
        )
        hdr_tbl.setStyle(TableStyle([
            ("ALIGN",          (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",     (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING",  (0, 0), (-1, -1), 2),
            ("LEFTPADDING",    (0, 0), (-1, -1), 2),
            ("RIGHTPADDING",   (0, 0), (-1, -1), 2),
            ("BACKGROUND",     (0, 0), (-1, -1), colors.HexColor(_C_ROW_ALT)),
            ("GRID",           (0, 0), (-1, -1), 0.3, colors.HexColor(_C_HR)),
            # Thicker bottom border separating header from subcats
            ("LINEBELOW",      (0, 1), (-1, 1), 1.0, colors.HexColor(_C_MID)),
            # Category name is smaller — achieved via the cr_cat style on the name part
        ]))

        # --- Subcategory table: 12 cols (name | value) × 6 categories ---
        # name col = cat_w * 0.68, value col = cat_w * 0.32
        sub_col_w: list[float] = []
        for _ in cats:
            sub_col_w.append(cat_w * 0.68)
            sub_col_w.append(cat_w * 0.32)

        max_sub = max(len(rows) for rows in cat_sub.values())
        sub_rows_data: list[list] = []
        for i in range(max_sub):
            row: list = []
            for cat in cats:
                sub_list = cat_sub[cat]
                if i < len(sub_list):
                    sub_name, cnt = sub_list[i]
                    row.append(Paragraph(_safe(sub_name), sty["cr_sub_n"]))
                    row.append(Paragraph(str(cnt),        sty["cr_sub_v"]))
                else:
                    row.append(Paragraph("", sty["cr_sub_n"]))
                    row.append(Paragraph("", sty["cr_sub_v"]))
            sub_rows_data.append(row)

        sub_tbl = Table(sub_rows_data, colWidths=sub_col_w)
        sub_ts = TableStyle([
            ("FONTSIZE",       (0, 0), (-1, -1), 7),
            ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",     (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING",  (0, 0), (-1, -1), 2),
            ("LEFTPADDING",    (0, 0), (-1, -1), 3),
            ("RIGHTPADDING",   (0, 0), (-1, -1), 3),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1),
             [colors.white, colors.HexColor(_C_ROW_ALT)]),
            ("GRID",           (0, 0), (-1, -1), 0.3, colors.HexColor(_C_HR)),
        ])
        # Thicker vertical separator between each category pair of columns
        for ci in range(1, n):
            col_idx = ci * 2
            sub_ts.add("LINEAFTER",  (col_idx - 1, 0), (col_idx - 1, -1),
                       0.8, colors.HexColor(_C_MID))
        sub_tbl.setStyle(sub_ts)

        return [hdr_tbl, sub_tbl]

    # -----------------------------------------------------------------------
    # Per-mission stats table (Duration / A/C Damage / Pilot Damage / Result)
    # – NO kills here
    # -----------------------------------------------------------------------
    def _stats_table(mission_json: dict, aircraft: str = "") -> Table:
        summary  = mission_json.get("summary", {}) if isinstance(mission_json, dict) else {}
        duration = _safe(summary.get("flight_duration") or "—")
        ac_dmg   = _pct(summary.get("aircraft_damage", 0))
        plt_dmg  = _pct(summary.get("pilot_damage", 0))
        result   = _safe(summary.get("final_state") or "—")

        header = [
            Paragraph("Duration",     sty["tbl_hdr"]),
            Paragraph("A/C Damage",   sty["tbl_hdr"]),
            Paragraph("Pilot Damage", sty["tbl_hdr"]),
            Paragraph("Result",       sty["tbl_hdr"]),
        ]
        data_row = [
            Paragraph(duration, sty["tbl_cell"]),
            Paragraph(ac_dmg,   sty["tbl_cell"]),
            Paragraph(plt_dmg,  sty["tbl_cell"]),
            Paragraph(result,   sty["tbl_cell"]),
        ]
        col_w = [CW * 0.20, CW * 0.20, CW * 0.20, CW * 0.40]
        t = Table([header, data_row], colWidths=col_w)
        t.setStyle(_tbl_style(header_rows=1))
        return t

    # -----------------------------------------------------------------------
    # Index: story chapters by day
    # -----------------------------------------------------------------------
    chapters_by_date: dict[str, dict] = {}
    for ch in (story_chapters or []):
        key = ch.get("mission_id") or ch.get("date") or ""
        if key:
            chapters_by_date[key] = ch

    all_events     = career_detail.get("events") or []
    all_incidences = career_detail.get("other_incidences") or []

    # -----------------------------------------------------------------------
    # Cover / pilot header
    # -----------------------------------------------------------------------
    flowables: list = []

    pilot_name  = _safe(career_detail.get("display_name") or
                        career_detail.get("pilot_name") or "Unknown Pilot")
    country     = _safe(career_detail.get("country") or "").title()
    birth       = _safe(career_detail.get("birth_date") or "")
    theatres    = " > ".join(
        _safe(t) for t in (career_detail.get("theatre_chain") or [])
    ) or "-"
    squadron    = _safe(career_detail.get("squadron_short_name") or "")
    role        = career_detail.get("pilot_role") or ""
    role_label  = {"commander": "Squadron Commander",
                   "deputy_commander": "Deputy Commander"}.get(role, "")

    summary    = career_detail.get("summary") or {}
    timeline   = summary.get("timeline") or {}
    first_date = _safe(timeline.get("first_mission_date") or "")
    last_date  = _safe(timeline.get("last_mission_date") or "")
    duration_d = timeline.get("duration_days")

    progression = summary.get("career_progression") or {}
    final_rank  = _safe(progression.get("final_rank") or "")

    flowables.append(Paragraph(pilot_name, sty["title"]))
    flowables.append(accent_bar())

    header_lines = []
    if final_rank:
        header_lines.append(f"<b>{final_rank}</b>")
    if country:
        header_lines.append(country)
    if squadron:
        line = squadron
        if role_label:
            line += f" ({role_label})"
        header_lines.append(line)
    if birth:
        header_lines.append(f"Born: {birth}")
    if first_date or last_date:
        period = f"{first_date or '?'} \u2013 {last_date or '?'}"
        if duration_d is not None:
            period += f"  ({duration_d} days)"
        header_lines.append(f"Career Period: {period}")
    if theatres and theatres != "-":
        header_lines.append(f"Theatres: {theatres}")

    for line in header_lines:
        flowables.append(Paragraph(line, sty["subtitle"]))

    flowables.append(Spacer(1, 8 * mm))

    # -----------------------------------------------------------------------
    # Per-day chapters
    # -----------------------------------------------------------------------
    for ctx_idx, ctx in enumerate(day_contexts or []):
        day_date   = ctx.get("date") or ctx.get("mission_id") or ""
        pilot      = ctx.get("pilot") or {}
        mission    = ctx.get("mission") or {}
        mprog      = ctx.get("mission_progression") or {}
        cprog      = ctx.get("career_progress") or {}
        ch_scope   = ctx.get("chapter_scope") or {}

        rank       = _safe(pilot.get("rank") or "")
        aircraft   = _safe(pilot.get("aircraft") or "")
        sqn        = _safe(pilot.get("squadron") or "")
        result     = _safe(mission.get("result") or "")
        chap_idx   = cprog.get("missions_completed") or (ctx_idx + 1)

        day_events      = _events_for_date(all_events, day_date)
        day_incidences  = _incidences_for_date(all_incidences, day_date)
        story_ch        = chapters_by_date.get(day_date)
        mission_jsons   = ch_scope.get("mission_jsons") or []

        section: list = []

        # --- Chapter header ---
        ch_label = f"Chapter {chap_idx}  |  {day_date}"
        if aircraft:
            ch_label += f"  |  {aircraft}"
        if result:
            ch_label += f"  |  {result}"
        section.append(Paragraph(_safe(ch_label), sty["ch_hdr"]))
        section.append(accent_bar())

        # --- Per-mission tables ---
        for mis_idx, mis_data in enumerate(mission_jsons):
            mis_json    = mis_data.get("json") or {}
            mis_id      = _safe(mis_data.get("mission_id") or f"{mis_idx + 1}")
            mis_aircraft = _safe(mis_data.get("aircraft") or aircraft or "")

            mis_label = f"Sortie {mis_idx + 1}"
            if mis_aircraft:
                mis_label += f"  —  {mis_aircraft}"
            section.append(Paragraph(mis_label, sty["mis_hdr"]))

            mis_sortie_stats = mis_data.get("sortie_stats") or {}
            combat_fls = _combat_results_flowables(mis_sortie_stats, mis_json)
            stats_tbl = _stats_table(mis_json, mis_aircraft)

            if combat_fls:
                section.append(_keep(combat_fls))
                section.append(Spacer(1, 2 * mm))
            else:
                section.append(Paragraph("No kills recorded.", sty["no_kills"]))

            section.append(_keep([stats_tbl]))
            section.append(Spacer(1, 3 * mm))

        # If no mission_jsons fall back (should not happen), emit a thin note
        if not mission_jsons:
            section.append(Paragraph(
                "Mission data not available.", sty["no_kills"]))

        # --- Other incidences ---
        if day_incidences:
            section.append(Spacer(1, 2 * mm))
            section.append(Paragraph("Other Incidences", sty["sec_hdr"]))
            for oi in day_incidences:
                section.append(Paragraph(
                    "• " + _safe(_format_incidence(oi)), sty["body"]))

        # --- Awards & Promotions ---
        # Use the display names from career_detail events (not image filenames).
        # Images doubled in size (IMG_SZ = 36 mm).
        award_event_rows: list[tuple[Optional[bytes], str]] = []

        for ev in day_events:
            ev_type  = ev.get("type") or ""
            img_url  = ev.get("image_url") or ev.get("modal_image_url") or ""
            img_bytes = _load_image_bytes(img_url, data_dir, game_dir)
            if ev_type == "promotion":
                # ev["rank"] is the display name ("Oberfeldwebel"), ev["rank_code"] is English key
                label = "Promoted to " + _safe(ev.get("rank") or ev.get("rank_code") or "")
            elif ev_type == "award":
                # ev["name"] is the name_key (e.g. "fighters_bronze") — resolve via locale
                name_key = str(ev.get("name") or ev.get("award_code") or "")
                label = _safe(_award_display_name(name_key) or name_key or "Award")
            else:
                label = _safe(ev_type.replace("_", " ").title())
            award_event_rows.append((img_bytes, label))

        # Fall back to mission_progression text when no event records exist
        if not award_event_rows:
            day_awards    = mprog.get("awards") or []
            day_promotion = _safe(mprog.get("promotion") or "")
            for aw in day_awards:
                aw_str = str(aw)
                award_event_rows.append((None, _safe(_award_display_name(aw_str) or aw_str)))
            if day_promotion:
                award_event_rows.append((None, "Promoted to " + day_promotion))

        if award_event_rows:
            section.append(Spacer(1, 3 * mm))
            section.append(Paragraph("Awards & Promotions", sty["sec_hdr"]))
            for img_bytes, label in award_event_rows:
                img_fl = img_flowable(img_bytes)
                if img_fl:
                    row_data = [[img_fl, Paragraph(label, sty["award_txt"])]]
                    row_tbl  = Table(
                        row_data,
                        colWidths=[IMG_SZ + 4 * mm, CW - IMG_SZ - 4 * mm],
                    )
                    row_tbl.setStyle(TableStyle([
                        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
                        ("LEFTPADDING",   (0, 0), (-1, -1), 2),
                        ("RIGHTPADDING",  (0, 0), (-1, -1), 2),
                        ("TOPPADDING",    (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]))
                    section.append(_keep([row_tbl]))
                else:
                    section.append(Paragraph("• " + label, sty["body"]))

        # --- AI Story ---
        if story_ch:
            story_title = _safe(story_ch.get("title") or "")
            story_text  = _safe(story_ch.get("story_text") or "")
            if story_title or story_text:
                section.append(Spacer(1, 4 * mm))
                section.append(hr())
            if story_title:
                section.append(Paragraph(story_title, sty["story_ttl"]))
            if story_text:
                paras = [p.strip() for p in story_text.split("\n\n") if p.strip()]
                for p in paras:
                    section.append(Paragraph(p.replace("\n", " "), sty["body"]))

        # Keep chapter header + first table together; rest flows freely
        if section:
            flowables.append(_keep(section[:4]))
            flowables.extend(section[4:])

        # Visual separator between chapters (no hard page break)
        flowables.append(Spacer(1, 6 * mm))
        flowables.append(hr())

    # -----------------------------------------------------------------------
    # Career Summary (final pages)
    # -----------------------------------------------------------------------
    summary_section: list = []
    summary_section.append(Paragraph("Career Summary", sty["smry_hdr"]))
    summary_section.append(accent_bar())
    summary_section.append(Spacer(1, 4 * mm))
    flowables.append(_keep(summary_section))

    # --- Combat results (screenshot-style, aggregated from all sortie stats) ---
    # Aggregate kill columns from every sortie across the whole career.
    summary_sortie_stats: dict[str, int] = {}
    for _ctx in (day_contexts or []):
        for _mis in (_ctx.get("chapter_scope") or {}).get("mission_jsons") or []:
            for _k, _v in (_mis.get("sortie_stats") or {}).items():
                try:
                    summary_sortie_stats[_k] = summary_sortie_stats.get(_k, 0) + int(_v or 0)
                except (TypeError, ValueError):
                    pass

    combat_res = summary.get("combat_results") or {}
    pcp = combat_res.get("pcp_score")

    cr_header_para = Paragraph("Combat Results", sty["sec_hdr"])
    # Summary uses aggregated cp.db stats; no per-aircraft breakdown from reports
    cr_fls = _combat_results_flowables(summary_sortie_stats, {})

    if cr_fls or pcp is not None:
        group: list = [cr_header_para]
        if pcp is not None:
            try:
                group.append(Paragraph(f"PCP Score: <b>{float(pcp):.1f}</b>", sty["body"]))
            except (TypeError, ValueError):
                pass
        group.extend(cr_fls)
        flowables.append(_keep(group))
        flowables.append(Spacer(1, 4 * mm))

    # --- Air kills by aircraft type ---
    kills_by_type = summary.get("air_kills_by_type") or {}
    if kills_by_type:
        ak_header = [
            Paragraph("Aircraft Type", sty["tbl_hdr"]),
            Paragraph("Kills",         sty["tbl_hdr"]),
        ]
        ak_rows: list[list] = [ak_header]
        total_air = 0
        for ac_type, count in sorted(kills_by_type.items(), key=lambda x: -x[1]):
            ak_rows.append([
                Paragraph(_safe(ac_type), sty["tbl_cell"]),
                Paragraph(str(count),     sty["tbl_cell"]),
            ])
            total_air += int(count or 0)
        ak_rows.append([
            Paragraph("<b>Total Air Kills</b>", sty["tbl_cell"]),
            Paragraph(f"<b>{total_air}</b>",    sty["tbl_cell"]),
        ])
        ak_tbl = Table(ak_rows, colWidths=[CW * 0.78, CW * 0.22])
        ak_ts = _tbl_style(header_rows=1)
        _bold_last_row(ak_ts, len(ak_rows) - 1)
        ak_tbl.setStyle(ak_ts)
        flowables.append(_keep([
            Paragraph("Air Kills by Aircraft Type", sty["sec_hdr"]),
            ak_tbl,
        ]))
        flowables.append(Spacer(1, 4 * mm))

    # --- Mission statistics ---
    mis_stats = summary.get("missions_stats") or {}
    ms_rows: list[tuple[str, str]] = []
    if mis_stats.get("total_missions") is not None:
        ms_rows.append(("Total Missions",       str(mis_stats["total_missions"])))
    if mis_stats.get("successful_missions") is not None:
        ms_rows.append(("Successful Missions",  str(mis_stats["successful_missions"])))
    if mis_stats.get("success_rate") is not None:
        try:
            ms_rows.append(("Success Rate", f"{float(mis_stats['success_rate']):.1f}%"))
        except (TypeError, ValueError):
            pass
    if mis_stats.get("total_flight_time"):
        ms_rows.append(("Total Flight Time",    _safe(mis_stats["total_flight_time"])))
    if mis_stats.get("average_duration"):
        ms_rows.append(("Avg. Mission Duration", _safe(mis_stats["average_duration"])))

    if ms_rows:
        ms_tbl = _kv_table(ms_rows)
        flowables.append(_keep([Paragraph("Mission Statistics", sty["sec_hdr"]), ms_tbl]))
        flowables.append(Spacer(1, 4 * mm))

    # --- Aircraft usage (campaign-style) ---
    aircraft_usage = summary.get("aircraft_usage") or {}
    if aircraft_usage:
        au_header = [
            Paragraph("Aircraft",  sty["tbl_hdr"]),
            Paragraph("Missions",  sty["tbl_hdr"]),
            Paragraph("Kills",     sty["tbl_hdr"]),
        ]
        au_rows = [au_header]
        for ac_name, ac_info in list(aircraft_usage.items())[:30]:
            ac_mis = ac_info.get("missions", 0) if isinstance(ac_info, dict) else 0
            ac_kil = ac_info.get("kills", 0)    if isinstance(ac_info, dict) else 0
            au_rows.append([
                Paragraph(_safe(ac_name), sty["tbl_cell"]),
                Paragraph(str(ac_mis),    sty["tbl_cell"]),
                Paragraph(str(ac_kil),    sty["tbl_cell"]),
            ])
        au_tbl = Table(au_rows, colWidths=[CW * 0.55, CW * 0.225, CW * 0.225])
        au_tbl.setStyle(_tbl_style(header_rows=1))
        flowables.append(_keep([Paragraph("Aircraft Flown", sty["sec_hdr"]), au_tbl]))
        flowables.append(Spacer(1, 4 * mm))

    # --- Career progression ---
    prog_rows: list[tuple[str, str]] = []
    if progression.get("starting_rank"):
        prog_rows.append(("Starting Rank",    _safe(progression["starting_rank"])))
    if progression.get("final_rank"):
        prog_rows.append(("Final Rank",       _safe(progression["final_rank"])))
    if progression.get("promotions_count") is not None:
        prog_rows.append(("Promotions",       str(progression["promotions_count"])))
    if progression.get("awards_count") is not None:
        prog_rows.append(("Awards Received",  str(progression["awards_count"])))
    awards_list = progression.get("awards_list") or []
    if awards_list:
        prog_rows.append(("Awards", ", ".join(
            _safe(_award_display_name(str(a)) or str(a)) for a in awards_list
        )))

    if prog_rows:
        pr_tbl = _kv_table(prog_rows)
        flowables.append(_keep([Paragraph("Career Progression", sty["sec_hdr"]), pr_tbl]))
        flowables.append(Spacer(1, 4 * mm))

    # --- Timeline ---
    tl_rows: list[tuple[str, str]] = []
    if first_date:
        tl_rows.append(("First Mission",     first_date))
    if last_date:
        tl_rows.append(("Last Mission",      last_date))
    if duration_d is not None:
        tl_rows.append(("Career Duration",   f"{duration_d} days"))
    if theatres and theatres != "-":
        tl_rows.append(("Theatres",          theatres))

    if tl_rows:
        tl_tbl = _kv_table(tl_rows)
        flowables.append(_keep([Paragraph("Timeline", sty["sec_hdr"]), tl_tbl]))

    return flowables


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def generate_career_pdf(
    career_id: int,
    career_detail: dict,
    day_contexts: list[dict],
    story_chapters: list[dict],
    output_dir: Path,
    data_dir: Optional[Path] = None,
    game_dir: Optional[Path] = None,
) -> Path:
    """Generate and save a career PDF report.

    Args:
        career_id:      Root career ID (used in filename).
        career_detail:  Dict from CareerAggregator.get_career_detail().
        day_contexts:   List from _build_career_story_contexts(); each dict must
                        include chapter_scope.mission_jsons with per-sortie data.
        story_chapters: List from load_story_chapters_for().
        output_dir:     Directory in which to save the PDF.
        data_dir:       Tracker data directory (for image resolution).
        game_dir:       IL-2 game directory (fallback for images).

    Returns:
        Path to the generated PDF file.

    Raises:
        ImportError: if reportlab is not installed.
        OSError: if the output directory cannot be created or written.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm as _mm
    from reportlab.platypus import SimpleDocTemplate

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename  = f"career_{career_id}_{timestamp}.pdf"
    out_path  = output_dir / filename

    MARGIN = 20

    def _footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        from reportlab.lib.colors import HexColor
        canvas.setFillColor(HexColor(_C_MID))
        pilot_name = _safe(career_detail.get("display_name") or "")
        canvas.drawCentredString(
            A4[0] / 2, 12 * _mm,
            f"{pilot_name}  \u2014  IL-2 Career Service Record  \u2014  Page {canvas.getPageNumber()}",
        )
        canvas.restoreState()

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=MARGIN * _mm,
        rightMargin=MARGIN * _mm,
        topMargin=MARGIN * _mm,
        bottomMargin=18 * _mm,
        title=f"Career Service Record \u2013 {_safe(career_detail.get('display_name', ''))}",
        author="IL-2 Career Service Record",
    )

    flowables = _build_story(
        career_detail=career_detail,
        day_contexts=day_contexts,
        story_chapters=story_chapters,
        data_dir=data_dir,
        game_dir=game_dir,
    )

    doc.build(flowables, onFirstPage=_footer, onLaterPages=_footer)
    logger.info("Career PDF saved: %s", out_path)
    return out_path
