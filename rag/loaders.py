from __future__ import annotations

from pathlib import Path

from config import Settings


def load_cv(settings: Settings) -> str:
    content = settings.cv_path.read_text(encoding="utf-8").strip()
    if not content:
        raise ValueError("master_cv.md is empty. Run python scripts/setup.py first.")
    return content


def load_job_description(description: str, title: str = "", company: str = "") -> str:
    header = f"Job: {title} at {company}\n\n" if title or company else ""
    return header + description


def load_file(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()
