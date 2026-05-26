"""
career_book_pdf.py

Generates a literary "Career Book" PDF for a finished career.

Structure:
  - Cover page
  - Prologue (AI-generated, Dan Brown style)
  - Per-theatre chapters:
      - Theatre heading
      - AI-synthesized narrative chapter (derived from mission stories, not the stories verbatim)
      - Award citations for that theatre
  - Epilogue (AI-generated, Dan Brown style)
  - Career statistics appendix

Requires: reportlab >= 4.0
"""

from __future__ import annotations

import io
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Colour palette (matches career_pdf_report.py for visual consistency)
# ---------------------------------------------------------------------------
_C_DARK    = "#1a2035"
_C_ACCENT  = "#b8962e"
_C_MID     = "#4a5568"
_C_ROW_ALT = "#f7f7f9"
_C_HR      = "#c0c0c0"
_C_CREAM   = "#faf4e8"   # parchment for framing sections


_UNICODE_MAP: dict[int, str] = {
    # Quotation marks
    0x2018: "'", 0x2019: "'", 0x201A: ",",
    0x201C: '"', 0x201D: '"', 0x201E: '"',
    # Dashes
    0x2013: "-", 0x2014: " - ", 0x2015: " - ",
    # Ellipsis / other punctuation
    0x2026: "...", 0x2022: "*", 0x2027: ".",
    # Arrows / angle quotes used as separators
    0x203A: ">", 0x2039: "<", 0x00BB: ">>", 0x00AB: "<<",
    # Spacing / formatting
    0x00A0: " ", 0x200B: "", 0xFEFF: "",
    # Fractions / math symbols likely to appear
    0x00D7: "x", 0x00F7: "/",
}


def _safe(text: Any, fallback: str = "") -> str:
    if text is None:
        return fallback
    out = []
    for c in str(text):
        o = ord(c)
        if o < 256:
            out.append(c)
        elif o in _UNICODE_MAP:
            out.append(_UNICODE_MAP[o])
        else:
            out.append("?")
    return "".join(out)


def _award_display_name(name_key: str) -> str:
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


def _load_image_bytes(
    image_url: Optional[str],
    data_dir: Optional[Path],
    game_dir: Optional[Path],
) -> Optional[bytes]:
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
# Theatre helpers
# ---------------------------------------------------------------------------

def _theatre_segments(career_detail: dict) -> list[dict]:
    """Return theatre segments sorted by start_date."""
    segs = list(career_detail.get("theatre_segments") or [])
    segs.sort(key=lambda s: str(s.get("start_date") or ""))
    return segs


def _theatre_for_date(date_str: str, segments: list[dict]) -> str:
    """Return the theatre label for a given date string."""
    theatre = ""
    for seg in segments:
        if str(seg.get("start_date") or "") <= date_str:
            theatre = str(seg.get("theatre") or "")
    return theatre


def _theatre_date_range(idx: int, segments: list[dict]) -> tuple[str, str]:
    """Return (start_date, end_date) for segment at idx. end_date="" if last."""
    start = str(segments[idx].get("start_date") or "")
    end = str(segments[idx + 1].get("start_date") or "") if idx + 1 < len(segments) else ""
    return start, end



def _citations_for_theatre(
    citations: dict,
    start_date: str,
    end_date: str,
) -> list[tuple[str, str]]:
    """Return [(award_name_key, citation_text)] for citations in this theatre's date range."""
    result = []
    for key, text in sorted(citations.items()):
        if not key.startswith("award|"):
            continue
        parts = key.split("|")
        # career: award|name|date  (3 parts)
        if len(parts) < 3:
            continue
        award_name = parts[1]
        date_part = parts[2]
        if date_part < start_date:
            continue
        if end_date and date_part >= end_date:
            continue
        result.append((award_name, _safe(text)))
    return result


# ---------------------------------------------------------------------------
# PDF builder
# ---------------------------------------------------------------------------

def _build_book_flowables(
    career_detail: dict,
    book_state: dict,
    citations: dict,
    data_dir: Optional[Path],
    game_dir: Optional[Path],
    pilot_photo_bytes: Optional[bytes] = None,
) -> list:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        HRFlowable, Image, KeepTogether, PageBreak,
        Paragraph, Spacer, Table, TableStyle,
    )

    PAGE_W, PAGE_H = A4
    MARGIN = 22 * mm
    CW = PAGE_W - 2 * MARGIN

    base = getSampleStyleSheet()

    def S(name: str, **kw) -> ParagraphStyle:
        parent = kw.pop("parent", "Normal")
        return ParagraphStyle(name, parent=base[parent], **kw)

    # Literary style set — more generous than service-record PDF
    sty = {
        "cover_title":  S("B_CoverTitle", parent="Heading1", fontSize=30,
                           alignment=TA_CENTER, spaceAfter=4,
                           textColor=colors.HexColor(_C_DARK)),
        "cover_sub":    S("B_CoverSub",   fontSize=12, alignment=TA_CENTER,
                           spaceAfter=6, textColor=colors.HexColor(_C_MID),
                           leading=18),
        "cover_dates":  S("B_CoverDates", fontSize=10, alignment=TA_CENTER,
                           textColor=colors.HexColor(_C_MID), leading=15),
        "section_hdr":  S("B_SecHdr",     parent="Heading1", fontSize=22,
                           spaceBefore=0, spaceAfter=4,
                           textColor=colors.HexColor(_C_DARK)),
        "theatre_hdr":  S("B_TheatreHdr", parent="Heading1", fontSize=18,
                           spaceBefore=0, spaceAfter=3,
                           textColor=colors.HexColor(_C_DARK)),
        "chapter_hdr":  S("B_ChHdr",      parent="Heading2", fontSize=13,
                           spaceBefore=14, spaceAfter=4,
                           textColor=colors.HexColor(_C_DARK)),
        "vignette":     S("B_Vignette",   fontSize=11, leading=17, spaceAfter=8,
                           alignment=TA_JUSTIFY, fontName="Helvetica-Oblique",
                           leftIndent=12, rightIndent=12,
                           textColor=colors.HexColor(_C_DARK)),
        "body":         S("B_Body",       fontSize=10, leading=16, spaceAfter=8,
                           alignment=TA_JUSTIFY,
                           textColor=colors.HexColor(_C_DARK)),
        "story_title":  S("B_StoryTtl",   fontSize=11, leading=15, spaceAfter=3,
                           fontName="Helvetica-Bold",
                           textColor=colors.HexColor(_C_DARK)),
        "citation_box": S("B_Citation",   fontSize=9, leading=14, spaceAfter=4,
                           alignment=TA_JUSTIFY,
                           fontName="Helvetica-Oblique",
                           leftIndent=16, rightIndent=16,
                           textColor=colors.HexColor(_C_MID)),
        "citation_hdr": S("B_CitHdr",     fontSize=9, spaceAfter=2,
                           fontName="Helvetica-Bold",
                           textColor=colors.HexColor(_C_DARK)),
        "appendix_hdr": S("B_AppHdr",     parent="Heading2", fontSize=14,
                           spaceBefore=0, spaceAfter=6,
                           textColor=colors.HexColor(_C_DARK)),
        "kv_label":     S("B_KvLabel",    fontSize=9, fontName="Helvetica-Bold"),
        "kv_val":       S("B_KvVal",      fontSize=9),
    }

    def hr() -> HRFlowable:
        return HRFlowable(
            width="100%", thickness=0.5,
            color=colors.HexColor(_C_HR),
            spaceAfter=3, spaceBefore=3,
        )

    def accent_bar() -> HRFlowable:
        return HRFlowable(
            width="100%", thickness=2.5,
            color=colors.HexColor(_C_ACCENT),
            spaceAfter=8, spaceBefore=2,
        )

    def _render_body(text: str) -> list:
        """Split on blank lines and render each paragraph."""
        out = []
        for para in [p.strip() for p in (text or "").split("\n\n") if p.strip()]:
            out.append(Paragraph(para.replace("\n", " "), sty["body"]))
        return out

    def _render_vignette(text: str) -> list:
        out = []
        for para in [p.strip() for p in (text or "").split("\n\n") if p.strip()]:
            out.append(Paragraph(para.replace("\n", " "), sty["vignette"]))
        return out

    segments = _theatre_segments(career_detail)
    pilot_name = _safe(
        career_detail.get("display_name") or career_detail.get("pilot_name") or "Unknown Pilot"
    )
    country = _safe(career_detail.get("country") or "").title()
    summary = career_detail.get("summary") or {}
    timeline = summary.get("timeline") or {}
    first_date = _safe(timeline.get("first_mission_date") or "")
    last_date = _safe(timeline.get("last_mission_date") or "")
    theatre_chain = list(career_detail.get("theatre_chain") or [])
    progression = summary.get("career_progression") or {}
    final_rank = _safe(progression.get("final_rank") or "")

    flowables: list = []

    # ── Cover page ──────────────────────────────────────────────────────────
    flowables.append(Spacer(1, 30 * mm))
    flowables.append(Paragraph(pilot_name, sty["cover_title"]))
    flowables.append(Spacer(1, 4 * mm))
    flowables.append(accent_bar())
    flowables.append(Spacer(1, 6 * mm))

    cover_lines = []
    if final_rank:
        cover_lines.append(f"<b>{final_rank}</b>")
    if country:
        cover_lines.append(country)
    if cover_lines:
        flowables.append(Paragraph("  —  ".join(cover_lines), sty["cover_sub"]))
        flowables.append(Spacer(1, 4 * mm))

    if first_date or last_date:
        flowables.append(Paragraph(
            f"{first_date or '?'}  to  {last_date or '?'}",
            sty["cover_dates"],
        ))
    if theatre_chain:
        flowables.append(Spacer(1, 3 * mm))
        flowables.append(Paragraph(
            "  ›  ".join(_safe(t) for t in theatre_chain),
            sty["cover_dates"],
        ))

    # Pilot photo on cover (best-effort)
    if pilot_photo_bytes:
        try:
            from career_pdf_report import _apply_photo_filter
            filtered = _apply_photo_filter(pilot_photo_bytes)
            from PIL import Image as PILImage
            with PILImage.open(io.BytesIO(filtered)) as _pi:
                _pw, _ph = _pi.size
            max_dim = 55 * mm
            if _pw >= _ph:
                dw, dh = max_dim, max_dim * _ph / _pw
            else:
                dh, dw = max_dim, max_dim * _pw / _ph
            photo_img = Image(io.BytesIO(filtered), width=dw, height=dh)
            photo_img.hAlign = "CENTER"
            flowables.append(Spacer(1, 8 * mm))
            flowables.append(photo_img)
        except Exception:
            pass

    flowables.append(Spacer(1, 20 * mm))
    flowables.append(Paragraph(
        "A War Record  —  IL-2 Career Service Record",
        sty["cover_dates"],
    ))

    # ── Prologue ────────────────────────────────────────────────────────────
    prologue = _safe(book_state.get("prologue") or "")
    if prologue:
        flowables.append(PageBreak())
        flowables.append(Spacer(1, 8 * mm))
        flowables.append(Paragraph("PROLOGUE", sty["section_hdr"]))
        flowables.append(accent_bar())
        flowables.append(Spacer(1, 4 * mm))
        flowables.extend(_render_body(prologue))

    # ── Theatre chapters ─────────────────────────────────────────────────────
    theatre_narratives = book_state.get("theatre_narratives") or {}
    roman = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]

    for idx, seg in enumerate(segments):
        theatre = str(seg.get("theatre") or "")
        start_date, end_date = _theatre_date_range(idx, segments)
        narrative_text = _safe(theatre_narratives.get(theatre) or "")
        theatre_citations = _citations_for_theatre(citations, start_date, end_date)

        if not narrative_text and not theatre_citations:
            continue

        roman_num = roman[idx] if idx < len(roman) else str(idx + 1)
        heading = f"Part {roman_num}  —  {theatre}"

        flowables.append(PageBreak())
        flowables.append(Spacer(1, 8 * mm))
        flowables.append(Paragraph(heading, sty["theatre_hdr"]))
        flowables.append(accent_bar())
        flowables.append(Spacer(1, 6 * mm))

        if narrative_text:
            flowables.extend(_render_body(narrative_text))

        # Award citations for this theatre
        if theatre_citations:
            flowables.append(Spacer(1, 8 * mm))
            flowables.append(hr())
            flowables.append(Paragraph("Decorations & Citations", sty["appendix_hdr"]))
            for award_name, citation_text in theatre_citations:
                display = _safe(_award_display_name(award_name) or award_name)
                cit_block: list = [
                    Paragraph(display, sty["citation_hdr"]),
                ]
                if citation_text:
                    cit_block.append(Paragraph(citation_text, sty["citation_box"]))
                cit_block.append(Spacer(1, 3 * mm))
                flowables.append(KeepTogether(cit_block[:2]))
                if len(cit_block) > 2:
                    flowables.extend(cit_block[2:])

    # ── Epilogue ─────────────────────────────────────────────────────────────
    epilogue = _safe(book_state.get("epilogue") or "")
    if epilogue:
        flowables.append(PageBreak())
        flowables.append(Spacer(1, 8 * mm))
        flowables.append(Paragraph("EPILOGUE", sty["section_hdr"]))
        flowables.append(accent_bar())
        flowables.append(Spacer(1, 4 * mm))
        flowables.extend(_render_body(epilogue))

    # ── Appendix: career statistics ──────────────────────────────────────────
    flowables.append(PageBreak())
    flowables.append(Spacer(1, 8 * mm))
    flowables.append(Paragraph("Appendix: Career Statistics", sty["appendix_hdr"]))
    flowables.append(accent_bar())
    flowables.append(Spacer(1, 4 * mm))

    def _kv_table(rows: list[tuple[str, str]]) -> Table:
        data = [
            [Paragraph(_safe(k), sty["kv_label"]), Paragraph(_safe(v), sty["kv_val"])]
            for k, v in rows
        ]
        t = Table(data, colWidths=[CW * 0.42, CW * 0.58])
        t.setStyle(TableStyle([
            ("FONTSIZE",       (0, 0), (-1, -1), 9),
            ("VALIGN",         (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor(_C_ROW_ALT)]),
            ("GRID",           (0, 0), (-1, -1), 0.3, colors.HexColor(_C_HR)),
            ("TOPPADDING",     (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING",  (0, 0), (-1, -1), 4),
            ("LEFTPADDING",    (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",   (0, 0), (-1, -1), 6),
        ]))
        return t

    stat_rows: list[tuple[str, str]] = []
    if final_rank:
        stat_rows.append(("Final Rank", final_rank))
    if country:
        stat_rows.append(("Country", country))
    if first_date:
        stat_rows.append(("First Mission", first_date))
    if last_date:
        stat_rows.append(("Last Mission", last_date))
    duration_d = timeline.get("duration_days")
    if duration_d is not None:
        stat_rows.append(("Career Duration", f"{duration_d} days"))
    if theatre_chain:
        stat_rows.append(("Theatres", "  ›  ".join(_safe(t) for t in theatre_chain)))

    mis_stats = summary.get("missions_stats") or {}
    if mis_stats.get("total_missions") is not None:
        stat_rows.append(("Total Missions", str(mis_stats["total_missions"])))
    if mis_stats.get("successful_missions") is not None:
        stat_rows.append(("Successful Missions", str(mis_stats["successful_missions"])))

    combat_results = summary.get("combat_results") or {}
    total_air = 0
    for seg_key in ["air_kills_by_type"]:
        for _, v in (summary.get(seg_key) or {}).items():
            try:
                total_air += int(v or 0)
            except (TypeError, ValueError):
                pass
    if total_air:
        stat_rows.append(("Total Air Victories", str(total_air)))

    if progression.get("starting_rank"):
        stat_rows.append(("Starting Rank", _safe(progression["starting_rank"])))
    if progression.get("promotions_count") is not None:
        stat_rows.append(("Promotions", str(progression["promotions_count"])))

    awards_list = progression.get("awards_list") or []
    if awards_list:
        stat_rows.append(("Awards Received", str(len(awards_list))))
        awards_text = ", ".join(
            _safe(_award_display_name(str(a)) or str(a)) for a in awards_list
        )
        stat_rows.append(("Decorations", awards_text))

    if stat_rows:
        flowables.append(_kv_table(stat_rows))

    return flowables


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_career_book_pdf(
    career_id: int,
    career_detail: dict,
    book_state: dict,
    citations: dict,
    output_dir: Path,
    data_dir: Optional[Path] = None,
    game_dir: Optional[Path] = None,
    pilot_photo_bytes: Optional[bytes] = None,
) -> Path:
    """Generate and save the career book PDF.

    Args:
        career_id:      Root career ID (used in filename).
        career_detail:  Dict from CareerAggregator.get_career_detail().
        book_state:     Dict from load_book_state_for() — prologue, theatre_narratives, epilogue.
        citations:      Dict from load_citations_for() — award citation texts.
        output_dir:     Directory in which to save the PDF.
        data_dir:       Tracker data directory (for image resolution).
        game_dir:       IL-2 game directory (fallback for images).
        pilot_photo_bytes: Optional raw photo bytes for the cover page.

    Returns:
        Path to the generated PDF file.
    """
    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm as _mm
    from reportlab.platypus.doctemplate import BaseDocTemplate, PageTemplate
    from reportlab.platypus.frames import Frame

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"career_{career_id}_book_{timestamp}.pdf"
    out_path = output_dir / filename

    MARGIN_MM = 22
    FOOTER_H = 12

    pilot_name = _safe(career_detail.get("display_name") or "")

    def _draw_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(HexColor(_C_MID))
        pw = canvas._pagesize[0]
        canvas.drawCentredString(
            pw / 2, FOOTER_H * _mm,
            f"{pilot_name}  —  IL-2 Career Book  —  Page {canvas.getPageNumber()}",
        )
        canvas.restoreState()

    A4_W, A4_H = A4
    m = MARGIN_MM * _mm
    frame = Frame(
        m, (FOOTER_H + 4) * _mm,
        A4_W - 2 * m,
        A4_H - m - (FOOTER_H + 4) * _mm,
    )
    template = PageTemplate("main", frames=[frame], onPage=_draw_footer)

    doc = BaseDocTemplate(
        str(out_path),
        pageTemplates=[template],
        pagesize=A4,
        leftMargin=m,
        rightMargin=m,
        topMargin=m,
        bottomMargin=(FOOTER_H + 4) * _mm,
        title=f"Career Book – {pilot_name}",
        author="IL-2 Career Service Record",
    )

    flowables = _build_book_flowables(
        career_detail=career_detail,
        book_state=book_state,
        citations=citations,
        data_dir=data_dir,
        game_dir=game_dir,
        pilot_photo_bytes=pilot_photo_bytes,
    )

    doc.build(flowables)
    logger.info("Career book PDF saved: %s", out_path)
    return out_path
