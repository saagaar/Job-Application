from __future__ import annotations

from pathlib import Path

from config import Settings, get_settings
from db.database import Database
from generators.docx_builder import DocxBuilder
from generators.pdf_renderer import PdfRenderer
from providers.llm_factory import create_llm


def generate_application(
    job_id: int,
    template: str = "professional",
    cover_letter_content: str | None = None,
    settings: Settings | None = None,
) -> dict[str, Path]:
    from agents.tailor_agent import TailorAgent

    settings = settings or get_settings()
    db = Database()
    job = db.get_job(job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found in database.")

    cv_content = settings.cv_path.read_text(encoding="utf-8").strip()
    if not cv_content:
        raise ValueError("master_cv.md is empty. Fill it in before generating applications.")

    llm = create_llm(settings, provider=settings.cv_llm_provider, model=settings.cv_llm_model)
    agent = TailorAgent(llm, settings)
    tailored = agent.tailor_cv(job.description, cv_content, job.company, job.title)

    builder = DocxBuilder()
    renderer = PdfRenderer()

    cv_docx = builder.build_cv(tailored, settings.person_name, job.company, template)
    cv_pdf = renderer.render_cv(cv_docx)

    paths: dict[str, Path] = {"cv_docx": cv_docx, "cv_pdf": cv_pdf}

    if cover_letter_content:
        cl_docx = builder.build_cover_letter(
            cover_letter_content, settings.person_name, job.company, template
        )
        cl_pdf = renderer.render_cover_letter(cl_docx)
        paths["cl_docx"] = cl_docx
        paths["cl_pdf"] = cl_pdf
        db.mark_as_applied(job_id, str(cv_docx), str(cl_docx))
    else:
        db.mark_as_applied(job_id, str(cv_docx), "")

    from services.job_service import _sync_exports
    _sync_exports(Database().get_all_jobs(), settings)
    return paths


def generate_cover_letter(
    job_id: int,
    person_name: str,
    settings: Settings | None = None,
) -> str:
    from agents.cover_letter_agent import CoverLetterAgent

    settings = settings or get_settings()
    db = Database()
    job = db.get_job(job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found.")

    cv_content = settings.cv_path.read_text(encoding="utf-8").strip()
    llm = create_llm(settings, provider=settings.cv_llm_provider, model=settings.cv_llm_model)
    agent = CoverLetterAgent(llm, settings)
    return agent.generate(job.description, cv_content, job.company, job.title, person_name)


def refine_cover_letter(
    draft: str,
    feedback: str,
    settings: Settings | None = None,
) -> str:
    from agents.cover_letter_agent import CoverLetterAgent

    settings = settings or get_settings()
    llm = create_llm(settings, provider=settings.cv_llm_provider, model=settings.cv_llm_model)
    agent = CoverLetterAgent(llm, settings)
    return agent.refine(draft, feedback)
