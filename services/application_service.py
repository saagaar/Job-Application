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
    from utils.cv_contact_parser import parse_contact

    settings = settings or get_settings()
    db = Database()
    job = db.get_job(job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found in database.")

    cv_content = settings.cv_path.read_text(encoding="utf-8").strip()
    if not cv_content:
        raise ValueError("master_cv.md is empty. Fill it in before generating applications.")

    personal_stories = ""
    if settings.personal_stories_path.exists():
        personal_stories = settings.personal_stories_path.read_text(encoding="utf-8").strip()

    contact = parse_contact(cv_content)
    person_name    = contact["name"]    or settings.person_name
    person_email   = contact["email"]   or settings.person_email
    person_phone   = contact["phone"]   or settings.person_phone
    person_address = contact["address"] or settings.person_address
    person_linkedin = contact["linkedin"] or settings.person_linkedin

    llm = create_llm(settings, provider=settings.cv_llm_provider, model=settings.cv_llm_model)
    agent = TailorAgent(llm, settings)
    tailored = agent.tailor_cv(
        job.description, cv_content, job.company, job.title,
        personal_stories=personal_stories,
    )

    builder = DocxBuilder()
    renderer = PdfRenderer()

    cv_docx = builder.build_cv(
        tailored, person_name, job.company, template,
        person_email=person_email,
        person_phone=person_phone,
        person_address=person_address,
        person_linkedin=person_linkedin,
        outputs_root=settings.outputs_path,
    )
    cv_pdf = renderer.render_cv(cv_docx)

    db.update_job(job_id, cv_path=str(cv_pdf))

    paths: dict[str, Path] = {"cv_docx": cv_docx, "cv_pdf": cv_pdf}

    if cover_letter_content:
        cl_docx = builder.build_cover_letter(
            cover_letter_content, person_name, job.company, template
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
    import json
    from agents.cover_letter_agent import CoverLetterAgent
    from services.company_research import research_company

    settings = settings or get_settings()
    db = Database()
    job = db.get_job(job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found.")

    cv_content = settings.cv_path.read_text(encoding="utf-8").strip()

    personal_stories = ""
    if settings.personal_stories_path.exists():
        personal_stories = settings.personal_stories_path.read_text(encoding="utf-8").strip()

    matching_skills = json.loads(job.match_skills) if job.match_skills else []
    gaps            = json.loads(job.match_gaps)   if job.match_gaps   else []
    reasoning       = job.match_reasoning or ""

    company_research = research_company(job.company)

    llm   = create_llm(settings, provider=settings.cv_llm_provider, model=settings.cv_llm_model)
    agent = CoverLetterAgent(llm, settings)
    return agent.generate(
        job.description, cv_content, job.company, job.title, person_name,
        matching_skills=matching_skills,
        gaps=gaps,
        reasoning=reasoning,
        personal_stories=personal_stories,
        company_research=company_research,
    )


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
