from __future__ import annotations

import importlib
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


class TemplateEngine:
    _cache: dict[str, dict] = {}

    def load(self, name: str = "professional") -> dict:
        if name in self._cache:
            return self._cache[name]
        module = importlib.import_module(f"templates.cv_template_{name}")
        self._cache[name] = module.TEMPLATE
        return module.TEMPLATE

    def apply_margins(self, doc, template: dict) -> None:
        from docx.shared import Inches
        margins = template.get("page_margins", {})
        for section in doc.sections:
            section.top_margin = Inches(margins.get("top", 1.0))
            section.bottom_margin = Inches(margins.get("bottom", 1.0))
            section.left_margin = Inches(margins.get("left", 1.0))
            section.right_margin = Inches(margins.get("right", 1.0))
