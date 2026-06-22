from __future__ import annotations

import re
from pathlib import Path

from fpdf import FPDF


def _safe_name(text: str) -> str:
    return re.sub(r"[^\w\s-]", "", text).strip().replace(" ", "_")


def _to_latin1(text: str) -> str:
    """Replace common Unicode punctuation with ASCII equivalents so fpdf doesn't choke."""
    replacements = {
        "‘": "'", "’": "'",   # curly single quotes
        "“": '"', "”": '"',   # curly double quotes
        "–": "-", "—": "--",  # en-dash, em-dash
        "…": "...",                # ellipsis
        " ": " ",                  # non-breaking space
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def render_cover_letter_pdf(
    content: str,
    person_name: str,
    company: str,
    outputs_root: Path,
) -> Path:
    """Write cover letter text to outputs/{company}/{person_name}_coverletter.pdf."""
    out_dir = outputs_root / _safe_name(company)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{_safe_name(person_name)}_coverletter.pdf"

    pdf = FPDF()
    pdf.set_margins(22, 28, 22)
    pdf.set_auto_page_break(auto=True, margin=22)
    pdf.add_page()

    # Name header
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(31, 56, 100)
    pdf.cell(0, 10, _to_latin1(person_name), ln=True, align="C")
    pdf.ln(6)

    # Body — split on blank lines to preserve paragraph breaks
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(30, 30, 30)
    for line in content.split("\n"):
        stripped = _to_latin1(line.strip())
        if not stripped:
            pdf.ln(5)
        else:
            pdf.multi_cell(0, 6, stripped)
            pdf.ln(1)

    pdf.output(str(out_path))
    return out_path
