from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from fpdf import FPDF


def _safe_name(text: str) -> str:
    return re.sub(r"[^\w\s-]", "", text).strip().replace(" ", "_")


def _to_latin1(text: str) -> str:
    """Replace common Unicode punctuation with ASCII equivalents so fpdf doesn't choke."""
    replacements = {
        "'": "'", "'": "'",
        "“": '"', "”": '"',
        "–": "-", "—": "--",
        "…": "...",
        " ": " ",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def _draw_linkedin_badge(pdf: FPDF, x: float, y: float) -> float:
    """Draw the LinkedIn 'in' badge at (x, y). Returns the badge width."""
    badge_w, badge_h = 6.5, 4.5

    # Blue rounded-looking rectangle (fpdf 1.7.2 has no rounded rects, use plain rect)
    pdf.set_fill_color(0, 119, 181)
    pdf.rect(x, y, badge_w, badge_h, "F")

    # White "in" text centred inside
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 7)
    pdf.set_xy(x, y + 0.3)
    pdf.cell(badge_w, badge_h - 0.3, "in", align="C")

    return badge_w


def render_cover_letter_pdf(
    content: str,
    person_name: str,
    company: str,
    outputs_root: Path,
    person_email: str = "",
    person_phone: str = "",
    person_address: str = "",
    person_linkedin: str = "",
) -> Path:
    """Render a professional cover letter PDF with letterhead."""
    out_dir = outputs_root / _safe_name(company)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{_safe_name(person_name)}_coverletter.pdf"

    NAVY   = (21, 43, 85)
    GREY   = (90, 90, 90)
    BODY   = (30, 30, 30)
    LI_BLU = (0, 119, 181)
    L_MAR  = 22
    R_MAR  = 22
    USABLE = 210 - L_MAR - R_MAR   # 166 mm

    pdf = FPDF()
    pdf.set_margins(L_MAR, 18, R_MAR)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    # ── Name ─────────────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 11, _to_latin1(person_name.upper()), ln=True, align="C")

    # ── Contact row: email | phone | address ─────────────────────────────────
    contact_parts = [p for p in [person_email, person_phone, person_address] if p.strip()]
    if contact_parts:
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*GREY)
        pdf.cell(0, 5, _to_latin1("   |   ".join(contact_parts)), ln=True, align="C")

    # ── LinkedIn row ─────────────────────────────────────────────────────────
    if person_linkedin.strip():
        li_url = _to_latin1(person_linkedin.strip())
        # Normalise: strip protocol, keep domain + path
        li_display = re.sub(r"^https?://", "", li_url).rstrip("/")

        badge_w = 6.5
        gap     = 1.5
        pdf.set_font("Helvetica", "", 9)
        url_w   = pdf.get_string_width(li_display)
        total_w = badge_w + gap + url_w

        # Centre the badge + URL together
        start_x = L_MAR + (USABLE - total_w) / 2
        y = pdf.get_y() + 2

        _draw_linkedin_badge(pdf, start_x, y)

        # URL in LinkedIn blue, right of badge
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*LI_BLU)
        pdf.set_xy(start_x + badge_w + gap, y + 0.3)
        pdf.cell(url_w + 1, 4.5, li_display)

        pdf.ln(7)
    else:
        pdf.ln(3)

    # ── Separator rule ────────────────────────────────────────────────────────
    pdf.set_draw_color(*NAVY)
    pdf.set_line_width(0.5)
    rule_y = pdf.get_y()
    pdf.line(L_MAR, rule_y, L_MAR + USABLE, rule_y)
    pdf.ln(7)

    # ── Date ─────────────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*GREY)
    pdf.cell(0, 6, date.today().strftime("%B %d, %Y"), ln=True)
    pdf.ln(5)

    # ── Body ─────────────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*BODY)

    for line in content.split("\n"):
        stripped = _to_latin1(line.strip())
        if not stripped:
            pdf.ln(4)
        else:
            pdf.multi_cell(0, 6, stripped)
            pdf.ln(1)

    pdf.output(str(out_path))
    return out_path
