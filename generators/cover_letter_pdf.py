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
        "‘": "'", "’": "'",
        "“": '"', "”": '"',
        "–": "-", "—": "--",
        "…": "...",
        " ": " ",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def render_cover_letter_pdf(
    content: str,
    person_name: str,
    company: str,
    outputs_root: Path,
    person_email: str = "",
    person_phone: str = "",
    person_address: str = "",
) -> Path:
    """Render a formatted cover letter PDF with letterhead to outputs/{company}/."""
    out_dir = outputs_root / _safe_name(company)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{_safe_name(person_name)}_coverletter.pdf"

    pdf = FPDF()
    pdf.set_margins(22, 20, 22)
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # ── Letterhead ────────────────────────────────────────────────────────────
    # Name — large, bold, dark blue, centred
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(31, 56, 100)
    pdf.cell(0, 10, _to_latin1(person_name), ln=True, align="C")

    # Contact line — email | phone | address, smaller, grey, centred
    contact_parts = [p for p in [person_email, person_phone, person_address] if p.strip()]
    if contact_parts:
        contact_line = "  |  ".join(contact_parts)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(90, 90, 90)
        pdf.cell(0, 6, _to_latin1(contact_line), ln=True, align="C")

    pdf.ln(3)

    # Horizontal rule
    pdf.set_draw_color(31, 56, 100)
    pdf.set_line_width(0.5)
    x = pdf.get_x()
    y = pdf.get_y()
    pdf.line(x, y, x + 166, y)
    pdf.ln(6)

    # Date
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(0, 6, date.today().strftime("%B %d, %Y"), ln=True)
    pdf.ln(4)

    # ── Body ──────────────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(30, 30, 30)

    for line in content.split("\n"):
        stripped = _to_latin1(line.strip())
        if not stripped:
            pdf.ln(4)
        else:
            pdf.multi_cell(0, 6, stripped)
            pdf.ln(1)

    pdf.output(str(out_path))
    return out_path
