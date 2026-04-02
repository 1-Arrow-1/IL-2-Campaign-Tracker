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
def _apply_photo_filter(img_bytes: bytes) -> bytes:
    """Apply the same CSS filter used on the detail page to the pilot photo:
    grayscale(100%) sepia(28%) saturate(110%) contrast(105%) brightness(102%).

    Implemented with Pillow only (no numpy dependency).
    Returns filtered PNG bytes, or the original bytes on any error.
    """
    try:
        from PIL import Image as PILImage, ImageEnhance, ImageOps

        img = PILImage.open(io.BytesIO(img_bytes)).convert("RGB")

        # 1. grayscale(100%) — full desaturate → 'L' image
        grey = ImageOps.grayscale(img)   # single-channel L

        # 2. sepia(28%) applied to the greyscale channel.
        # For a grey value L, the full CSS sepia matrix (all channels equal = L) gives:
        #   R_sepia = L * (0.393 + 0.769 + 0.189) = L * 1.351
        #   G_sepia = L * (0.349 + 0.686 + 0.168) = L * 1.203
        #   B_sepia = L * (0.272 + 0.534 + 0.131) = L * 0.937
        # At 28% blend: channel = (1 - 0.28) * L + 0.28 * L * factor
        #   R factor = 0.72 + 0.28 * 1.351 = 1.098
        #   G factor = 0.72 + 0.28 * 1.203 = 1.057
        #   B factor = 0.72 + 0.28 * 0.937 = 0.982
        lut_r = bytes(min(255, int(i * 1.098)) for i in range(256))
        lut_g = bytes(min(255, int(i * 1.057)) for i in range(256))
        lut_b = bytes(min(255, int(i * 0.982)) for i in range(256))
        r = grey.point(lut_r)
        g = grey.point(lut_g)
        b = grey.point(lut_b)
        img = PILImage.merge("RGB", [r, g, b])

        # 3. saturate(110%)
        img = ImageEnhance.Color(img).enhance(1.10)

        # 4. contrast(105%)
        img = ImageEnhance.Contrast(img).enhance(1.05)

        # 5. brightness(102%)
        img = ImageEnhance.Brightness(img).enhance(1.02)

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    except Exception:
        return img_bytes   # silently fall back to original


def _composite_showcase_image(
    showcase_data: dict,
    data_dir: Optional[Path],
    game_dir: Optional[Path],
) -> Optional[bytes]:
    """Composite the medal showcase into a single RGBA PNG using Pillow.

    Layers (bottom to top): canvas → medals → overlay.
    Medal positioning mirrors the JS logic:
      - If img_w/img_h are known, the PNG is treated as a padded canvas
        and we crop from (img_x, img_y) with slot size (w, h).
      - Otherwise the image is scaled to fit the slot (contain).

    Returns PNG bytes, or None when Pillow is unavailable or canvas fails.
    """
    try:
        from PIL import Image as PILImage
    except ImportError:
        logger.warning("career_pdf: Pillow not installed — showcase page skipped")
        return None

    try:
        # 1. Canvas background
        canvas_bytes = _load_image_bytes(
            showcase_data.get("canvas_url") or "", data_dir, game_dir
        )
        if not canvas_bytes:
            logger.warning("career_pdf: showcase canvas not found")
            return None

        canvas = PILImage.open(io.BytesIO(canvas_bytes)).convert("RGBA")
        cw, ch = canvas.size

        # 2. Paste each earned medal
        for medal in (showcase_data.get("medals") or []):
            mx = int(medal.get("x", 0))
            my = int(medal.get("y", 0))
            mw = int(medal.get("w", 0))
            mh = int(medal.get("h", 0))
            img_w = int(medal.get("img_w") or 0)
            img_h = int(medal.get("img_h") or 0)
            img_x = int(medal.get("img_x") or 0)
            img_y = int(medal.get("img_y") or 0)

            if mw <= 0 or mh <= 0:
                continue

            medal_bytes = _load_image_bytes(
                medal.get("image_url") or "", data_dir, game_dir
            )
            if not medal_bytes:
                continue

            medal_img = PILImage.open(io.BytesIO(medal_bytes)).convert("RGBA")

            if img_w and img_h:
                # Crop content region: starts at (img_x, img_y) in the padded PNG,
                # size = slot (mw x mh), clamped to actual image bounds.
                cx0 = min(img_x, medal_img.width)
                cy0 = min(img_y, medal_img.height)
                cx1 = min(img_x + mw, medal_img.width)
                cy1 = min(img_y + mh, medal_img.height)
                cropped = medal_img.crop((cx0, cy0, cx1, cy1))
                if cropped.size != (mw, mh):
                    cropped = cropped.resize((mw, mh), PILImage.LANCZOS)
            else:
                # Fallback: fit within slot, centered
                medal_img.thumbnail((mw, mh), PILImage.LANCZOS)
                padded = PILImage.new("RGBA", (mw, mh), (0, 0, 0, 0))
                ox = (mw - medal_img.width) // 2
                oy = (mh - medal_img.height) // 2
                padded.paste(medal_img, (ox, oy), medal_img)
                cropped = padded

            # Use alpha_composite (Porter-Duff "over") to avoid white halos
            # that result from paste() compositing semi-transparent edge pixels
            # against white instead of the actual canvas background.
            layer = PILImage.new("RGBA", canvas.size, (0, 0, 0, 0))
            layer.paste(cropped, (mx, my))
            canvas = PILImage.alpha_composite(canvas, layer)

        # 3. Overlay on top
        ovl = showcase_data.get("overlay") or {}
        if ovl:
            ovl_bytes = _load_image_bytes(ovl.get("url") or "", data_dir, game_dir)
            ovl_w = int(ovl.get("w") or 0)
            ovl_h = int(ovl.get("h") or 0)
            if ovl_bytes and ovl_w and ovl_h:
                ovl_img = PILImage.open(io.BytesIO(ovl_bytes)).convert("RGBA")
                if ovl_img.size != (ovl_w, ovl_h):
                    ovl_img = ovl_img.resize((ovl_w, ovl_h), PILImage.LANCZOS)
                ovl_x = int(ovl.get("x") or 0)
                ovl_y = int(ovl.get("y") or 0)
                ovl_layer = PILImage.new("RGBA", canvas.size, (0, 0, 0, 0))
                ovl_layer.paste(ovl_img, (ovl_x, ovl_y))
                canvas = PILImage.alpha_composite(canvas, ovl_layer)

        # 4. Serialise to PNG bytes
        buf = io.BytesIO()
        canvas.save(buf, format="PNG")
        return buf.getvalue()

    except Exception as exc:
        logger.warning("career_pdf: showcase compositing failed: %s", exc, exc_info=True)
        return None


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


def _sort_mission_token(value: Any) -> tuple[int, str]:
    text = _safe(value).strip()
    if not text:
        return (1, "")
    try:
        return (0, f"{int(text):012d}")
    except (TypeError, ValueError):
        return (1, text)


def _normalize_day_contexts_for_pdf(day_contexts: list[dict]) -> list[dict]:
    """Merge mission-scoped contexts into the day-scoped layout used by the PDF."""
    sortable_contexts = [
        ctx for ctx in (day_contexts or [])
        if isinstance(ctx, dict) and _safe(ctx.get("date") or ctx.get("mission_id")).strip()
    ]
    sortable_contexts.sort(
        key=lambda ctx: (
            _safe(ctx.get("date") or "").strip(),
            _sort_mission_token(ctx.get("mission_id")),
        )
    )

    grouped: dict[str, list[dict]] = {}
    ordered_dates: list[str] = []
    for ctx in sortable_contexts:
        date_key = _safe(ctx.get("date") or ctx.get("mission_id")).strip()
        if date_key not in grouped:
            grouped[date_key] = []
            ordered_dates.append(date_key)
        grouped[date_key].append(ctx)

    normalized: list[dict] = []
    for date_key in ordered_dates:
        group = grouped.get(date_key) or []
        if not group:
            continue

        first = group[0]
        last = group[-1]

        mission_jsons: list[dict] = []
        mission_ids: list[str] = []
        aircraft_values: list[str] = []
        result_values: list[str] = []
        award_values: list[str] = []
        promotion_values: list[str] = []

        for ctx in group:
            chapter_scope = ctx.get("chapter_scope") or {}
            scope_jsons = chapter_scope.get("mission_jsons") or []
            if isinstance(scope_jsons, list):
                mission_jsons.extend(scope_jsons)

            scope_ids = chapter_scope.get("mission_ids") or []
            if isinstance(scope_ids, list):
                mission_ids.extend(_safe(mid).strip() for mid in scope_ids if _safe(mid).strip())

            ctx_mission_id = _safe(ctx.get("mission_id")).strip()
            if ctx_mission_id:
                mission_ids.append(ctx_mission_id)

            aircraft = _safe((ctx.get("pilot") or {}).get("aircraft")).strip()
            if aircraft:
                aircraft_values.append(aircraft)

            result = _safe((ctx.get("mission") or {}).get("result")).strip()
            if result:
                result_values.append(result)

            mission_progression = ctx.get("mission_progression") or {}
            awards = mission_progression.get("awards") or []
            if isinstance(awards, list):
                for award in awards:
                    award_text = _safe(award).strip()
                    if award_text and award_text not in award_values:
                        award_values.append(award_text)

            promotion = _safe(mission_progression.get("promotion")).strip()
            if promotion and promotion not in promotion_values:
                promotion_values.append(promotion)

        pilot_payload = dict(first.get("pilot") or {})
        mission_payload = dict(last.get("mission") or first.get("mission") or {})
        career_progress = dict(last.get("career_progress") or first.get("career_progress") or {})
        mission_progress = dict(first.get("mission_progression") or {})
        chapter_scope = dict(first.get("chapter_scope") or {})

        unique_aircraft = list(dict.fromkeys(aircraft_values))
        if len(unique_aircraft) == 1:
            pilot_payload["aircraft"] = unique_aircraft[0]
        elif len(unique_aircraft) > 1:
            pilot_payload["aircraft"] = ""

        unique_results = list(dict.fromkeys(result_values))
        if len(unique_results) == 1:
            mission_payload["result"] = unique_results[0]
        elif len(unique_results) > 1:
            mission_payload["result"] = "Multiple Sorties"

        chapter_scope["scope"] = "day"
        chapter_scope["mission_jsons"] = mission_jsons
        chapter_scope["mission_ids"] = list(dict.fromkeys(mission_ids))
        chapter_scope["missions_in_chapter"] = len(mission_jsons) or max(
            int(chapter_scope.get("missions_in_chapter", 1) or 1),
            len(group),
        )

        mission_progress["awards"] = award_values
        mission_progress["promotion"] = ", ".join(promotion_values)

        normalized_ctx = dict(first)
        normalized_ctx["date"] = date_key
        normalized_ctx["mission_id"] = _safe(last.get("mission_id") or first.get("mission_id")).strip()
        normalized_ctx["pilot"] = pilot_payload
        normalized_ctx["mission"] = mission_payload
        normalized_ctx["career_progress"] = career_progress
        normalized_ctx["mission_progression"] = mission_progress
        normalized_ctx["chapter_scope"] = chapter_scope
        normalized.append(normalized_ctx)

    return normalized


def _group_story_chapters_by_date(story_chapters: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for chapter in (story_chapters or []):
        if not isinstance(chapter, dict):
            continue
        date_key = _safe(chapter.get("date") or "").strip()
        if not date_key:
            continue
        grouped.setdefault(date_key, []).append(chapter)

    for chapters in grouped.values():
        chapters.sort(
            key=lambda chapter: (
                int(chapter.get("chapter_index") or 0),
                _sort_mission_token(chapter.get("mission_id")),
                _safe(chapter.get("title")).strip(),
            )
        )

    return grouped


def _group_story_chapters_by_mission(story_chapters: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for chapter in (story_chapters or []):
        if not isinstance(chapter, dict):
            continue
        mission_id = _safe(chapter.get("mission_id")).strip()
        date_key = _safe(chapter.get("date")).strip()
        if not mission_id or mission_id == date_key or mission_id.startswith("day:"):
            continue
        grouped.setdefault(mission_id, []).append(chapter)

    for chapters in grouped.values():
        chapters.sort(
            key=lambda chapter: (
                int(chapter.get("chapter_index") or 0),
                _safe(chapter.get("date")).strip(),
                _safe(chapter.get("title")).strip(),
            )
        )

    return grouped


# ---------------------------------------------------------------------------
# PDF flowable builder
# ---------------------------------------------------------------------------
def _build_story(
    career_detail: dict,
    day_contexts: list[dict],
    story_chapters: list[dict],
    data_dir: Optional[Path],
    game_dir: Optional[Path],
    pilot_photo_bytes: Optional[bytes] = None,
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
    IMG_SZ  = 54 * mm                  # fallback size for award/rank images
    IMG_SCALE = 0.35                   # render awards/ranks at 50% of source size
    MIN_TEXT_W = 30 * mm               # keep some width for the text column

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
        # Flight log
        "fl_hdr":    S("R_FlHdr",     fontSize=8,  fontName="Helvetica-Bold",
                        spaceBefore=5, spaceAfter=2,
                        textColor=colors.HexColor(_C_DARK)),
        "fl_time":   S("R_FlTime",    fontSize=8,  fontName="Courier",
                        textColor=colors.HexColor(_C_MID)),
        "fl_desc":   S("R_FlDesc",    fontSize=8,  fontName="Helvetica",
                        textColor=colors.HexColor(_C_DARK)),
    }

    day_contexts = _normalize_day_contexts_for_pdf(day_contexts)

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

    def _rank_big_url(url: Optional[str]) -> Optional[str]:
        if not url:
            return None
        prefix = "/api/career_assets/CampaignRanksAwards/"
        if not url.startswith(prefix):
            return url
        rel = url[len(prefix):]
        parent, name = rel.rsplit("/", 1) if "/" in rel else ("", rel)
        stem, ext = Path(name).stem, Path(name).suffix
        # Preserve existing big/big1 if already present
        if stem.endswith(("_big", "_big1")):
            filename = stem + (ext if ext else ".png")
        else:
            filename = f"{stem}_big.png"
        return f"{prefix}{parent + '/' if parent else ''}{filename}"

    def _award_big1_url(url: Optional[str]) -> Optional[str]:
        if not url:
            return None
        prefix = "/api/career_assets/CampaignRanksAwards/"
        if not url.startswith(prefix):
            return url
        rel = url[len(prefix):]
        parent, name = rel.rsplit("/", 1) if "/" in rel else ("", rel)
        stem = Path(name).stem
        ext_out = ".dds"
        # Normalize to *_big.dds
        if stem.endswith("_big1"):
            stem = stem[:-5]  # strip _big1
        if stem.endswith("_big"):
            stem = stem[:-4]
        filename = f"{stem}_big{ext_out}"
        return f"{prefix}{parent + '/' if parent else ''}{filename}"

    def _event_image_bytes(ev: dict) -> Optional[bytes]:
        """Select the preferred image bytes for an award/promotion event."""
        ev_type = ev.get("type", "")
        url_candidates: list[str] = []
        if ev_type == "promotion":
            url_candidates.extend([
                ev.get("modal_image_url"),
                _rank_big_url(ev.get("image_url")),
                ev.get("image_url"),
            ])
        elif ev_type == "award":
            url_candidates.extend([
                _award_big1_url(ev.get("image_url")),
                _award_big1_url(ev.get("modal_image_url")),
                ev.get("modal_image_url"),
                ev.get("image_url"),
            ])
        else:
            url_candidates.extend([ev.get("image_url"), ev.get("modal_image_url")])

        for url in url_candidates:
            img_bytes = _load_image_bytes(url or "", data_dir, game_dir)
            if img_bytes:
                return img_bytes
        return None

    def img_flowable(img_bytes: Optional[bytes]) -> Optional[Image]:
        if not img_bytes:
            return None
        try:
            img = Image(io.BytesIO(img_bytes))
            scaled_w = img.imageWidth * IMG_SCALE
            scaled_h = img.imageHeight * IMG_SCALE
            max_w = CW - 4 * mm - MIN_TEXT_W
            if scaled_w > max_w:
                scale = max_w / scaled_w
                scaled_w *= scale
                scaled_h *= scale
            img.drawWidth = scaled_w
            img.drawHeight = scaled_h
            return img
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
            # No background, no grid — clean white
            # Thick horizontal line below the count/name row
            ("LINEBELOW",      (0, 1), (-1, 1), 1.5, colors.HexColor(_C_DARK)),
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
            # No grid, no row backgrounds — clean white
        ])
        # Thin vertical separator between each category group (after the value col of each group)
        for ci in range(1, n):
            col_idx = ci * 2
            sub_ts.add("LINEAFTER", (col_idx - 1, 0), (col_idx - 1, -1),
                       0.5, colors.HexColor(_C_HR))
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
    # Flight log block — timestamped event list for a single mission
    # -----------------------------------------------------------------------
    _FL_DISPLAY = {"Takeoff", "Landing", "Kill", "Bailout", "Pilot Touchdown", "Damage Taken"}
    _FL_TIME_W  = 16 * mm

    def _flight_log_flowables(mis_json: dict) -> list:
        """Return [header, table] for the flight log, or [] if no events."""
        events = mis_json.get("events") or [] if isinstance(mis_json, dict) else []
        rows: list[tuple[str, str]] = []
        for ev in events:
            if not isinstance(ev, dict):
                continue
            ev_type = ev.get("type") or ""
            if ev_type not in _FL_DISPLAY:
                continue
            time_str = _safe(ev.get("time") or "")
            if ev_type == "Kill":
                target = _safe(ev.get("target") or "Unknown")
                alt    = ev.get("altitude")
                desc   = f"{target} destroyed"
                if alt is not None:
                    desc += f" (Alt: {alt}m)"
            elif ev_type == "Damage Taken":
                dmg  = _safe(ev.get("damage") or "")
                desc = f"Damage taken: {dmg}" if dmg else "Damage Taken"
            elif ev_type == "Pilot Touchdown":
                desc = "Pilot Touchdown"
            else:
                desc = ev_type   # "Takeoff", "Landing", "Bailout"
            rows.append((time_str, desc))

        if not rows:
            return []

        tbl_data = [
            [Paragraph(t, sty["fl_time"]), Paragraph(d, sty["fl_desc"])]
            for t, d in rows
        ]
        tbl = Table(tbl_data, colWidths=[_FL_TIME_W, CW - _FL_TIME_W])
        tbl.setStyle(TableStyle([
            ("FONTSIZE",       (0, 0), (-1, -1), 8),
            ("VALIGN",         (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING",     (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING",  (0, 0), (-1, -1), 1),
            ("LEFTPADDING",    (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",   (0, 0), (-1, -1), 2),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1),
             [colors.white, colors.HexColor(_C_ROW_ALT)]),
        ]))
        return [Paragraph("FLIGHT LOG", sty["fl_hdr"]), tbl]

    # -----------------------------------------------------------------------
    # Index: story chapters by day
    # -----------------------------------------------------------------------
    chapters_by_date = _group_story_chapters_by_date(story_chapters)
    chapters_by_mission = _group_story_chapters_by_mission(story_chapters)

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

    flowables.append(Spacer(1, 4 * mm))
    flowables.append(Paragraph(pilot_name, sty["title"]))
    flowables.append(Spacer(1, 3 * mm))
    flowables.append(accent_bar())
    flowables.append(Spacer(1, 3 * mm))

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

    # Build cover subtitle block — two-column when pilot photo is available
    _PHOTO_MAX = 40 * mm   # max dimension (width or height) for pilot photo on cover
    _filtered_photo = _apply_photo_filter(pilot_photo_bytes) if pilot_photo_bytes else None
    _photo_fl: Optional[Image] = None
    if _filtered_photo:
        try:
            from PIL import Image as _PIL_ph
            with _PIL_ph.open(io.BytesIO(_filtered_photo)) as _ph:
                _ph_w, _ph_h = _ph.size
            # Scale so the longest side = _PHOTO_MAX, preserving aspect ratio
            if _ph_w >= _ph_h:
                _draw_w = _PHOTO_MAX
                _draw_h = _PHOTO_MAX * _ph_h / _ph_w
            else:
                _draw_h = _PHOTO_MAX
                _draw_w = _PHOTO_MAX * _ph_w / _ph_h
            _photo_fl = Image(io.BytesIO(_filtered_photo), width=_draw_w, height=_draw_h)
        except Exception:
            pass
    # Column width matches the actual rendered photo width (not always _PHOTO_MAX).
    _PHOTO_COL = _draw_w if _photo_fl else _PHOTO_MAX

    if _photo_fl:
        # Left column: subtitle text lines  |  Right column: framed photo
        _txt_col  = CW - _PHOTO_COL - 6 * mm
        _left_cell = [Paragraph(ln, sty["subtitle"]) for ln in header_lines] or [Paragraph("", sty["subtitle"])]
        _cover_tbl = Table(
            [[_left_cell, _photo_fl]],
            colWidths=[_txt_col, _PHOTO_COL],
        )
        _cover_tbl.setStyle(TableStyle([
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
            ("TOPPADDING",    (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            # Thin gold border around the photo cell
            ("BOX",           (1, 0), (1, 0), 1.0, colors.HexColor(_C_ACCENT)),
        ]))
        flowables.append(_cover_tbl)
    else:
        for line in header_lines:
            flowables.append(Paragraph(line, sty["subtitle"]))

    flowables.append(Spacer(1, 8 * mm))

    # -----------------------------------------------------------------------
    # Per-day chapters — merged timeline: sortie days + event-only days
    # -----------------------------------------------------------------------
    # Build a lookup so the loop can find the full context for any sortie day.
    ctx_by_date: dict[str, dict] = {}
    for _ctx_item in (day_contexts or []):
        _d = _ctx_item.get("date") or _ctx_item.get("mission_id") or ""
        if _d:
            ctx_by_date[_d] = _ctx_item

    # Collect promotion/award events that fall on days with NO sortie.
    # These are completely invisible if we only iterate day_contexts.
    event_only: dict[str, list[dict]] = {}
    for _ev in all_events:
        _ev_type = _ev.get("type", "")
        _ev_date = _ev.get("date", "")
        if _ev_type in ("promotion", "award") and _ev_date and _ev_date not in ctx_by_date:
            event_only.setdefault(_ev_date, []).append(_ev)

    # Merged sorted timeline (sortie days + event-only days)
    all_chapter_dates = sorted(set(list(ctx_by_date.keys()) + list(event_only.keys())))

    # Helper: render the awards/promotions block shared by both chapter types
    def _render_award_block(evs: list[dict], fallback_mprog: dict) -> list:
        rows: list[tuple[Optional[bytes], str]] = []
        for ev in evs:
            ev_type   = ev.get("type") or ""
            img_bytes = _event_image_bytes(ev)
            if ev_type == "promotion":
                lbl = "Promoted to " + _safe(ev.get("rank") or ev.get("rank_code") or "")
            elif ev_type == "award":
                nk = str(ev.get("name") or ev.get("award_code") or "")
                lbl = _safe(_award_display_name(nk) or nk or "Award")
            else:
                lbl = _safe(ev_type.replace("_", " ").title())
            rows.append((img_bytes, lbl))

        if not rows and fallback_mprog:
            for aw in (fallback_mprog.get("awards") or []):
                aw_s = str(aw)
                rows.append((None, _safe(_award_display_name(aw_s) or aw_s)))
            day_promo = _safe(fallback_mprog.get("promotion") or "")
            if day_promo:
                rows.append((None, "Promoted to " + day_promo))

        if not rows:
            return []

        hdr_para = Paragraph("Awards & Promotions", sty["sec_hdr"])
        item_flowables: list = []
        for img_bytes, lbl in rows:
            img_fl = img_flowable(img_bytes)
            if img_fl:
                img_w = getattr(img_fl, "drawWidth", IMG_SZ)
                text_w = CW - img_w - 4 * mm
                if text_w < MIN_TEXT_W:
                    # Clamp image width so the text column keeps minimum width
                    excess = MIN_TEXT_W - text_w
                    img_w = max(0, img_w - excess)
                    if img_w > 0 and img_fl.drawWidth > 0:
                        scale = img_w / img_fl.drawWidth
                        img_fl.drawWidth = img_w
                        img_fl.drawHeight *= scale
                    text_w = MIN_TEXT_W
                rt = Table(
                    [[img_fl, Paragraph(lbl, sty["award_txt"])]],
                    colWidths=[img_w + 4 * mm, text_w],
                )
                rt.setStyle(TableStyle([
                    ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING",   (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING",  (0, 0), (-1, -1), 2),
                    ("TOPPADDING",    (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]))
                item_flowables.append(rt)
            else:
                item_flowables.append(Paragraph("• " + lbl, sty["body"]))

        # Keep header + first item together so the header never orphans at page bottom
        out: list = [Spacer(1, 3 * mm)]
        if item_flowables:
            out.append(_keep([hdr_para, item_flowables[0]]))
            for extra in item_flowables[1:]:
                out.append(_keep([extra]))
        else:
            out.append(hdr_para)
        return out

    def _story_ref(chapter: dict) -> tuple[str, str, int]:
        return (
            _safe(chapter.get("date")).strip(),
            _safe(chapter.get("mission_id")).strip(),
            int(chapter.get("chapter_index") or 0),
        )

    def _append_story_block(section: list, story_items: list[dict], *, first_block: bool) -> bool:
        appended = False
        for story_ch in story_items:
            story_title = _safe(story_ch.get("title") or "")
            story_text  = _safe(story_ch.get("story_text") or "")
            if not (story_title or story_text):
                continue
            if not appended and first_block:
                section.append(Spacer(1, 4 * mm))
                section.append(hr())
            else:
                section.append(Spacer(1, 2 * mm))
            if story_title:
                section.append(Paragraph(story_title, sty["story_ttl"]))
            if story_text:
                for p in [p.strip() for p in story_text.split("\n\n") if p.strip()]:
                    section.append(Paragraph(p.replace("\n", " "), sty["body"]))
            appended = True
            first_block = False
        return appended

    chapter_num = 0  # counts sortie chapters only (for fallback chap_idx)

    for date_key in all_chapter_dates:

        # ---- EVENT-ONLY DAY (promotion/award, no sortie) ----
        if date_key not in ctx_by_date:
            ev_evs = event_only.get(date_key, [])
            section: list = []
            section.append(Paragraph(
                _safe(f"Promotion / Award  |  {date_key}"), sty["ch_hdr"]))
            section.append(accent_bar())
            section.extend(_render_award_block(ev_evs, {}))

            if section:
                flowables.append(_keep(section[:3]))
                flowables.extend(section[3:])
            flowables.append(Spacer(1, 6 * mm))
            flowables.append(hr())
            continue

        # ---- SORTIE DAY (full chapter) ----
        chapter_num += 1
        ctx        = ctx_by_date[date_key]
        day_date   = date_key
        pilot      = ctx.get("pilot") or {}
        mission    = ctx.get("mission") or {}
        mprog      = ctx.get("mission_progression") or {}
        cprog      = ctx.get("career_progress") or {}
        ch_scope   = ctx.get("chapter_scope") or {}

        aircraft   = _safe(pilot.get("aircraft") or "")
        result     = _safe(mission.get("result") or "")
        chap_idx   = chapter_num

        day_events     = _events_for_date(all_events, day_date)
        day_incidences = _incidences_for_date(all_incidences, day_date)
        day_story_chapters = chapters_by_date.get(day_date, [])
        mission_jsons  = ch_scope.get("mission_jsons") or []
        rendered_story_refs: set[tuple[str, str, int]] = set()

        section = []

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
            mis_json     = mis_data.get("json") or {}
            mis_id       = _safe(mis_data.get("mission_id") or "")
            mis_aircraft = _safe(mis_data.get("aircraft") or aircraft or "")

            mis_label = f"Sortie {mis_idx + 1}"
            if mis_aircraft:
                mis_label += f"  —  {mis_aircraft}"
            sortie_intro: list = [Paragraph(mis_label, sty["mis_hdr"])]

            combat_fls = _combat_results_flowables(mis_data.get("sortie_stats") or {}, mis_json)
            stats_tbl  = _stats_table(mis_json, mis_aircraft)

            if combat_fls:
                sortie_intro.extend(combat_fls)
            else:
                sortie_intro.append(Paragraph("No kills recorded.", sty["no_kills"]))

            sortie_intro.append(stats_tbl)
            section.append(_keep(sortie_intro))
            section.append(Spacer(1, 2 * mm))

            fl_fls = _flight_log_flowables(mis_json)
            if fl_fls:
                section.append(_keep(fl_fls[:2]))   # keep header + first table row together
                section.append(Spacer(1, 3 * mm))
            else:
                section.append(Spacer(1, 1 * mm))

            mission_story_chapters = chapters_by_mission.get(mis_id, [])
            if mission_story_chapters:
                appended_story = _append_story_block(section, mission_story_chapters, first_block=True)
                if appended_story:
                    rendered_story_refs.update(_story_ref(ch) for ch in mission_story_chapters)

        if not mission_jsons:
            section.append(Paragraph("Mission data not available.", sty["no_kills"]))

        # --- Other incidences ---
        if day_incidences:
            section.append(Spacer(1, 2 * mm))
            section.append(Paragraph("Other Incidences", sty["sec_hdr"]))
            for oi in day_incidences:
                section.append(Paragraph(
                    "• " + _safe(_format_incidence(oi)), sty["body"]))

        # --- Awards & Promotions ---
        section.extend(_render_award_block(day_events, mprog))

        # --- AI Story ---
        remaining_day_stories = [
            story_ch for story_ch in day_story_chapters
            if _story_ref(story_ch) not in rendered_story_refs
        ]
        _append_story_block(section, remaining_day_stories, first_block=True)

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
    # "Career Summary" heading — built up front so we can keep it with first content
    _smry_hdr_flowables: list = [
        Paragraph("Career Summary", sty["smry_hdr"]),
        accent_bar(),
        Spacer(1, 4 * mm),
    ]

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
        # Keep "Career Summary" heading together with the combat results block
        group: list = _smry_hdr_flowables + [cr_header_para]
        if pcp is not None:
            try:
                group.append(Paragraph(f"PCP Score: <b>{float(pcp):.1f}</b>", sty["body"]))
            except (TypeError, ValueError):
                pass
        group.extend(cr_fls)
        flowables.append(_keep(group))
        flowables.append(Spacer(1, 4 * mm))
    else:
        # No combat results — emit heading on its own, keep with next section
        flowables.append(_keep(_smry_hdr_flowables))

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
    showcase_data: Optional[dict] = None,
    pilot_photo_bytes: Optional[bytes] = None,
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
        showcase_data:  Optional dict from build_showcase_data(); when provided,
                        a medal showcase page is appended as the final page in the
                        orientation that best fits the canvas aspect ratio.

    Returns:
        Path to the generated PDF file.

    Raises:
        ImportError: if reportlab is not installed.
        OSError: if the output directory cannot be created or written.
    """
    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import A4, landscape as rl_landscape
    from reportlab.lib.units import mm as _mm
    from reportlab.platypus import Image, NextPageTemplate, PageBreak
    from reportlab.platypus.doctemplate import BaseDocTemplate, PageTemplate
    from reportlab.platypus.frames import Frame

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename  = f"career_{career_id}_{timestamp}.pdf"
    out_path  = output_dir / filename

    MARGIN_MM = 20
    FOOTER_H  = 12  # mm from bottom

    pilot_name = _safe(career_detail.get("display_name") or "")

    def _draw_footer(canvas, doc):
        """Shared footer: centred at 12 mm from the bottom of whatever page is current."""
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(HexColor(_C_MID))
        pw = canvas._pagesize[0]
        canvas.drawCentredString(
            pw / 2, FOOTER_H * _mm,
            f"{pilot_name}  \u2014  IL-2 Career Service Record  \u2014  Page {canvas.getPageNumber()}",
        )
        canvas.restoreState()

    A4_W, A4_H = A4  # portrait: ~595 × 842 pt

    def _portrait_frame(pw: float, ph: float) -> Frame:
        m = MARGIN_MM * _mm
        return Frame(
            m, (FOOTER_H + 4) * _mm,
            pw - 2 * m,
            ph - m - (FOOTER_H + 4) * _mm,
        )

    # --- Portrait template (all regular pages) ---
    p_frame    = _portrait_frame(A4_W, A4_H)
    p_template = PageTemplate("portrait", frames=[p_frame], onPage=_draw_footer)

    # --- Composite showcase image (if showcase_data provided) ---
    showcase_png_bytes: Optional[bytes] = None
    showcase_use_landscape = False
    if showcase_data:
        showcase_png_bytes = _composite_showcase_image(showcase_data, data_dir, game_dir)
        if showcase_png_bytes:
            try:
                _img_tmp = io.BytesIO(showcase_png_bytes)
                from PIL import Image as PILImage
                with PILImage.open(_img_tmp) as _pi:
                    _iw, _ih = _pi.size
                showcase_use_landscape = (_iw > _ih)
            except Exception:
                showcase_use_landscape = True  # most career canvases are wider

    # --- Showcase page template (portrait or landscape) ---
    if showcase_use_landscape:
        SC_W, SC_H = rl_landscape(A4)   # ~842 × 595 pt
    else:
        SC_W, SC_H = A4_W, A4_H
    sc_frame    = _portrait_frame(SC_W, SC_H)
    sc_template = PageTemplate(
        "showcase",
        frames=[sc_frame],
        pagesize=(SC_W, SC_H),
        onPage=_draw_footer,
    )

    doc = BaseDocTemplate(
        str(out_path),
        pageTemplates=[p_template, sc_template],
        pagesize=A4,
        leftMargin=MARGIN_MM * _mm,
        rightMargin=MARGIN_MM * _mm,
        topMargin=MARGIN_MM * _mm,
        bottomMargin=(FOOTER_H + 4) * _mm,
        title=f"Career Service Record \u2013 {pilot_name}",
        author="IL-2 Career Service Record",
    )

    flowables = _build_story(
        career_detail=career_detail,
        day_contexts=day_contexts,
        story_chapters=story_chapters,
        data_dir=data_dir,
        game_dir=game_dir,
        pilot_photo_bytes=pilot_photo_bytes,
    )

    # --- Append showcase page ---
    if showcase_png_bytes:
        # Usable area on the showcase page
        m = MARGIN_MM * _mm
        usable_w = SC_W - 2 * m
        usable_h = SC_H - m - (FOOTER_H + 4) * _mm

        try:
            showcase_img = Image(
                io.BytesIO(showcase_png_bytes),
                width=usable_w,
                height=usable_h,
                kind="proportional",   # scale uniformly to fit
            )
            showcase_img.hAlign = "CENTER"

            flowables.append(NextPageTemplate("showcase"))
            flowables.append(PageBreak())
            flowables.append(showcase_img)
        except Exception as exc:
            logger.warning("career_pdf: failed to add showcase image: %s", exc)

    doc.build(flowables)
    logger.info("Career PDF saved: %s", out_path)
    return out_path
