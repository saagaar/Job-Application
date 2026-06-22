from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

from docx import Document
from fpdf import FPDF


def _to_latin1(text: str) -> str:
    """Sanitise Unicode punctuation so fpdf 1.7.2 (latin-1 only) doesn't crash."""
    replacements = {
        "–": "-", "—": "--",   # en-dash, em-dash
        "‘": "'", "’": "'",    # curly single quotes
        "“": '"', "”": '"',    # curly double quotes
        "…": "...",                 # ellipsis
        " ": " ",                   # non-breaking space
        "•": "-",                   # bullet
        "■": "-",                   # black square bullet
        "●": "-",                   # filled circle bullet
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text.encode("latin-1", errors="replace").decode("latin-1")


class PdfRenderer:
    def render_cv(self, docx_path: Path, output_path: Optional[Path] = None) -> Path:
        out = output_path or docx_path.with_suffix(".pdf")
        if self._try_macos_textutil(docx_path, out):
            return out
        return self._render_with_fpdf(docx_path, out)

    def render_cover_letter(self, docx_path: Path, output_path: Optional[Path] = None) -> Path:
        out = output_path or docx_path.with_suffix(".pdf")
        if self._try_macos_textutil(docx_path, out):
            return out
        return self._render_with_fpdf(docx_path, out, top_margin=25)

    def _render_with_fpdf(self, docx_path: Path, out_path: Path, top_margin: int = 20) -> Path:
        doc = Document(docx_path)
        elements = self._docx_to_elements(doc)

        pdf = _JobPDF()
        pdf.set_margins(20, top_margin, 20)
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.add_page()

        for el in elements:
            kind     = el["type"]
            text     = _to_latin1(el["text"])
            centered = el.get("centered", False)

            if not text.strip():
                pdf.ln(3)
                continue

            if kind == "name_header":
                pdf.set_font("Helvetica", "B", 18)
                pdf.set_text_color(31, 56, 100)
                pdf.cell(0, 10, text, ln=True, align="C")
            elif kind == "heading1":
                pdf.ln(4)
                pdf.set_font("Helvetica", "B", 12)
                pdf.set_text_color(31, 56, 100)
                pdf.cell(0, 7, text.upper(), ln=True)
                pdf.set_draw_color(46, 116, 181)
                pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 170, pdf.get_y())
                pdf.ln(1)
            elif kind == "heading2":
                pdf.set_font("Helvetica", "B", 11)
                pdf.set_text_color(46, 116, 181)
                pdf.cell(0, 6, text, ln=True)
            elif kind == "bullet":
                pdf.set_font("Helvetica", "", 10)
                pdf.set_text_color(0, 0, 0)
                pdf.set_x(pdf.get_x() + 5)
                pdf.multi_cell(0, 5, f"- {text}")
            elif kind == "italic":
                pdf.set_font("Helvetica", "I", 9)
                pdf.set_text_color(100, 100, 100)
                pdf.multi_cell(0, 5, text)
            else:
                pdf.set_font("Helvetica", "", 10)
                pdf.set_text_color(0, 0, 0)
                if centered:
                    pdf.cell(0, 5, text, ln=True, align="C")
                else:
                    pdf.multi_cell(0, 5, text)

        pdf.output(str(out_path))
        return out_path

    def _docx_to_elements(self, doc: Document) -> list[dict]:
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        elements = []
        paragraphs = list(doc.paragraphs)
        for i, para in enumerate(paragraphs):
            text = para.text.strip()
            style_name = (para.style.name or "").lower()
            centered = para.alignment == WD_ALIGN_PARAGRAPH.CENTER

            if i == 0 and para.runs and para.runs[0].font.size and para.runs[0].font.size.pt >= 16:
                kind = "name_header"
            elif "heading 1" in style_name or (para.runs and any(r.font.size and r.font.size.pt >= 13 for r in para.runs)):
                kind = "heading1"
            elif "heading 2" in style_name or (para.runs and any(r.font.bold and r.font.size and r.font.size.pt >= 11 for r in para.runs)):
                kind = "heading2"
            elif "list bullet" in style_name:
                kind = "bullet"
            elif para.runs and all(r.font.italic for r in para.runs if r.text.strip()):
                kind = "italic"
            else:
                kind = "body"

            elements.append({"type": kind, "text": text, "centered": centered})
        return elements

    def _try_macos_textutil(self, docx_path: Path, pdf_path: Path) -> bool:
        # macOS: convert docx → html → pdf via cupsfilter (requires Word or LibreOffice not needed)
        try:
            html_path = docx_path.with_suffix(".html")
            result = subprocess.run(
                ["textutil", "-convert", "html", "-output", str(html_path), str(docx_path)],
                capture_output=True, timeout=30,
            )
            if result.returncode != 0 or not html_path.exists():
                return False
            # Use cupsfilter to convert html → pdf
            result2 = subprocess.run(
                ["cupsfilter", str(html_path), "-o", str(pdf_path)],
                capture_output=True, timeout=30,
            )
            html_path.unlink(missing_ok=True)
            return result2.returncode == 0 and pdf_path.exists()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False


class _JobPDF(FPDF):
    def header(self):
        pass

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")
