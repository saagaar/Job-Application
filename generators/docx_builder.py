from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Inches, Pt, RGBColor

from generators.template_engine import TemplateEngine

ROOT = Path(__file__).parent.parent
RESUMES_DIR = ROOT / "resumes" / "tailored"
CL_DIR = ROOT / "outputs" / "cover_letters"

_engine = TemplateEngine()


def _safe_filename(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text).strip()
    return re.sub(r"[\s]+", "_", text)


def _hex_to_rgb(hex_color: str) -> RGBColor:
    h = hex_color.lstrip("#")
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _apply_font(run, font_def: dict) -> None:
    run.font.name = font_def.get("name", "Calibri")
    run.font.size = Pt(font_def.get("size", 10))
    run.font.bold = font_def.get("bold", False)
    run.font.color.rgb = _hex_to_rgb(font_def.get("color", "000000"))


def _add_divider(doc: Document) -> None:
    p = doc.add_paragraph()
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "4")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "2E74B5")
    pBdr.append(bottom)
    pPr.append(pBdr)
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(2)


def _add_section_heading(doc: Document, text: str, fonts: dict, spacing: dict) -> None:
    _add_divider(doc)
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(spacing.get("before_section_pt", 10))
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run(text.upper())
    _apply_font(run, fonts["heading1"])


class DocxBuilder:
    def build_cv(
        self,
        tailored_data: dict,
        person_name: str,
        company: str,
        template_name: str = "professional",
    ) -> Path:
        RESUMES_DIR.mkdir(parents=True, exist_ok=True)
        template = _engine.load(template_name)
        fonts = template["fonts"]
        spacing = template["spacing"]
        doc = Document()
        _engine.apply_margins(doc, template)

        # Name header
        name_p = doc.add_paragraph()
        name_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        name_run = name_p.add_run(person_name)
        _apply_font(name_run, fonts["name_header"])
        name_p.paragraph_format.space_after = Pt(2)

        # Contact line (pulled from summary if present, else left blank)
        summary: str = tailored_data.get("summary", "")
        if summary:
            _add_section_heading(doc, "Professional Summary", fonts, spacing)
            for line in summary.split("\n"):
                line = line.strip()
                if line:
                    p = doc.add_paragraph()
                    p.paragraph_format.space_after = Pt(2)
                    run = p.add_run(line)
                    _apply_font(run, fonts["body"])

        # Experience
        experience = tailored_data.get("experience", [])
        if experience:
            _add_section_heading(doc, "Experience", fonts, spacing)
            for entry in experience:
                # Role title + company on one line
                p = doc.add_paragraph()
                p.paragraph_format.space_before = Pt(6)
                p.paragraph_format.space_after = Pt(0)
                title_run = p.add_run(f"{entry.get('title', '')}  —  {entry.get('company', '')}")
                _apply_font(title_run, fonts["heading2"])

                # Dates + location
                meta = f"{entry.get('dates', '')}  |  {entry.get('location', '')}".strip(" |")
                if meta:
                    p2 = doc.add_paragraph()
                    p2.paragraph_format.space_after = Pt(2)
                    run2 = p2.add_run(meta)
                    _apply_font(run2, fonts["dates"])

                # Bullets
                for bullet in entry.get("bullets", []):
                    bp = doc.add_paragraph(style="List Bullet")
                    bp.paragraph_format.left_indent = Inches(spacing.get("bullet_indent_cm", 0.5) / 2.54)
                    bp.paragraph_format.space_after = Pt(1)
                    brun = bp.add_run(bullet.lstrip("•- ").strip())
                    _apply_font(brun, fonts["bullet"])

        # Skills
        skills: dict = tailored_data.get("skills", {})
        if skills:
            _add_section_heading(doc, "Skills", fonts, spacing)
            for category, items in skills.items():
                if items:
                    p = doc.add_paragraph()
                    p.paragraph_format.space_after = Pt(2)
                    label_run = p.add_run(f"{category.capitalize()}: ")
                    _apply_font(label_run, {**fonts["body"], "bold": True})
                    val_run = p.add_run(", ".join(items))
                    _apply_font(val_run, fonts["body"])

        # Education
        education = tailored_data.get("education", [])
        if education:
            _add_section_heading(doc, "Education", fonts, spacing)
            for edu in education:
                p = doc.add_paragraph()
                p.paragraph_format.space_after = Pt(2)
                degree_run = p.add_run(f"{edu.get('degree', '')}  —  {edu.get('institution', '')}")
                _apply_font(degree_run, fonts["heading2"])
                year_note = f"{edu.get('year', '')}  {edu.get('notes', '')}".strip()
                if year_note:
                    p2 = doc.add_paragraph()
                    p2.paragraph_format.space_after = Pt(2)
                    _apply_font(p2.add_run(year_note), fonts["dates"])

        out_path = RESUMES_DIR / f"CV_{_safe_filename(person_name)}_{_safe_filename(company)}.docx"
        doc.save(out_path)
        return out_path

    def build_cover_letter(
        self,
        content: str,
        person_name: str,
        company: str,
        template_name: str = "professional",
    ) -> Path:
        CL_DIR.mkdir(parents=True, exist_ok=True)
        template = _engine.load(template_name)
        fonts = template["fonts"]
        doc = Document()
        _engine.apply_margins(doc, template)

        for line in content.split("\n"):
            line = line.strip()
            if not line:
                doc.add_paragraph()
                continue
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(6)
            run = p.add_run(line)
            _apply_font(run, fonts["body"])

        out_path = CL_DIR / f"Cover_Letter_{_safe_filename(person_name)}_{_safe_filename(company)}.docx"
        doc.save(out_path)
        return out_path
