from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_db
from config import get_settings
from providers.llm_factory import llm_error_message
from api.schemas import (
    ScoreResponse,
    SingleJobScoreResponse,
    CoverLetterResponse,
    CVGenerateResponse,
    GenerateRequest,
    GenerateResponse,
    ImportRequest,
    ImportResponse,
    InterviewPrepResponse,
    JobListResponse,
    ScrapeRequest,
    ScrapeResponse,
    UpdateJobRequest,
)
from db.database import Database
from db.models import Job, JobStatus
from services import application_service, interview_service, job_service

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=JobListResponse)
def list_jobs(status: Optional[JobStatus] = None, min_score: float = 0.0):
    jobs = job_service.get_jobs(status=status, min_score=min_score)
    return {"jobs": jobs, "total": len(jobs)}


@router.post("/scrape", response_model=ScrapeResponse)
def scrape_jobs(req: ScrapeRequest):
    import os

    cv_content = ""
    if not req.skip_scoring:
        cv_content = get_settings().cv_path.read_text(encoding="utf-8").strip()
        if not cv_content:
            raise HTTPException(status_code=400, detail="master_cv.md is empty. Fill it in first.")

    before = len(job_service.get_jobs())
    job_service.find_and_score_jobs(
        sources=req.sources,
        location=req.location,
        max_per_source=req.max_per_source,
        cv_content=cv_content,
        skip_scoring=req.skip_scoring,
    )
    after = len(job_service.get_jobs())
    return {"jobs_found": after, "jobs_new": after - before}


@router.post("/import", response_model=ImportResponse)
def import_jobs(req: ImportRequest, db: Database = Depends(get_db)):
    from datetime import datetime, timezone
    from db.models import Job as JobModel

    imported = skipped = 0
    new_ids: list[int] = []

    for item in req.jobs:
        job = JobModel(
            title=item.title,
            company=item.company,
            url=item.url,
            location=item.location,
            description=item.description,
            source=item.source,
            date_found=datetime.now(timezone.utc),
        )
        job_id = db.insert_job(job)
        if job_id is None:
            skipped += 1
        else:
            imported += 1
            new_ids.append(job_id)

    scored = 0
    if req.score and new_ids:
        try:
            from agents.match_agent import MatchAgent
            from providers.llm_factory import create_llm
            settings = get_settings()
            cv_content = settings.cv_path.read_text(encoding="utf-8").strip()
            if cv_content:
                from services.job_service import _load_target_roles
                target_roles = _load_target_roles(settings)
                llm = create_llm(settings, provider=settings.match_llm_provider, model=settings.match_llm_model)
                agent = MatchAgent(llm, settings, target_roles)
                unscored = [j for j in db.get_unscored_jobs() if j.id in new_ids]
                raw_list = [{"id": j.id, "description": j.description} for j in unscored]
                agent.batch_score(raw_list, cv_content)
                for item in raw_list:
                    if item.get("match_score") is not None:
                        db.update_job(item["id"], match_score=item["match_score"])
                        scored += 1
        except Exception:
            pass

    from services.job_service import _sync_exports
    _sync_exports(db.get_all_jobs(), get_settings())

    return {"imported": imported, "skipped": skipped, "scored": scored}


@router.post("/score", response_model=ScoreResponse)
def score_jobs(db: Database = Depends(get_db)):
    """Score all unscored jobs in the database against the master CV."""
    from agents.match_agent import MatchAgent
    from providers.llm_factory import create_llm
    from services.job_service import _load_target_roles, _sync_exports

    settings = get_settings()
    cv_content = settings.cv_path.read_text(encoding="utf-8").strip()
    if not cv_content:
        raise HTTPException(status_code=400, detail="master_cv.md is empty — fill it in first.")

    unscored = db.get_unscored_jobs()
    if not unscored:
        return {"scored": 0, "failed": 0}

    target_roles = _load_target_roles(settings)
    llm = create_llm(settings, provider=settings.match_llm_provider, model=settings.match_llm_model)
    agent = MatchAgent(llm, settings, target_roles)

    # Call score_job() directly rather than batch_score() — batch_score uses
    # Rich Progress which blocks in a non-TTY server context.
    # Fail fast on the first error to avoid burning retries across all jobs.
    scored = failed = 0
    last_error = ""
    for job in unscored:
        try:
            result = agent.score_job(job.description, cv_content)
            import json
            db.update_job(
                job.id,
                match_score=result["score"],
                match_skills=json.dumps(result["matching_skills"]),
                match_gaps=json.dumps(result["gaps"]),
                match_reasoning=result["reasoning"],
            )
            scored += 1
        except Exception as e:
            last_error = llm_error_message(e)
            failed += 1
            if scored == 0 and failed == 1:
                break  # stop immediately on first failure — likely a config/auth error

    _sync_exports(db.get_all_jobs(), settings)
    return {"scored": scored, "failed": failed, "error": last_error}


@router.post("/{job_id}/score", response_model=SingleJobScoreResponse)
def score_job_by_id(job_id: int, db: Database = Depends(get_db)):
    from agents.match_agent import MatchAgent
    from providers.llm_factory import create_llm
    from services.job_service import _load_target_roles, _sync_exports

    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    settings = get_settings()
    cv_content = settings.cv_path.read_text(encoding="utf-8").strip()
    if not cv_content:
        raise HTTPException(status_code=400, detail="master_cv.md is empty — fill it in first.")

    target_roles = _load_target_roles(settings)
    llm = create_llm(settings, provider=settings.match_llm_provider, model=settings.match_llm_model)
    agent = MatchAgent(llm, settings, target_roles)

    try:
        result = agent.score_job(job.description, cv_content)
    except Exception as e:
        raise HTTPException(status_code=502, detail=llm_error_message(e))

    import json
    db.update_job(
        job_id,
        match_score=result["score"],
        match_skills=json.dumps(result["matching_skills"]),
        match_gaps=json.dumps(result["gaps"]),
        match_reasoning=result["reasoning"],
    )
    _sync_exports(db.get_all_jobs(), settings)

    return {
        "job_id": job_id,
        "score": result["score"],
        "matching_skills": result["matching_skills"],
        "gaps": result["gaps"],
        "reasoning": result["reasoning"],
    }


@router.post("/{job_id}/cv", response_model=CVGenerateResponse)
def generate_cv_endpoint(job_id: int, db: Database = Depends(get_db)):
    """Generate a tailored CV (DOCX + PDF) for a specific job."""
    from generators.docx_builder import DocxBuilder
    from generators.pdf_renderer import PdfRenderer
    from agents.tailor_agent import TailorAgent
    from providers.llm_factory import create_llm
    from services.job_service import _sync_exports
    from utils.cv_contact_parser import parse_contact

    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    settings = get_settings()
    cv_content = settings.cv_path.read_text(encoding="utf-8").strip()
    if not cv_content:
        raise HTTPException(status_code=400, detail="master_cv.md is empty — fill it in first.")

    personal_stories = ""
    if settings.personal_stories_path.exists():
        personal_stories = settings.personal_stories_path.read_text(encoding="utf-8").strip()

    contact = parse_contact(cv_content)
    person_name     = contact["name"]     or settings.person_name
    person_email    = contact["email"]    or settings.person_email
    person_phone    = contact["phone"]    or settings.person_phone
    person_address  = contact["address"]  or settings.person_address
    person_linkedin = contact["linkedin"] or settings.person_linkedin

    try:
        llm    = create_llm(settings, provider=settings.cv_llm_provider, model=settings.cv_llm_model)
        agent  = TailorAgent(llm, settings)
        tailored = agent.tailor_cv(
            job.description, cv_content, job.company, job.title,
            personal_stories=personal_stories,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=llm_error_message(e))

    template = settings.cv_template or "professional"
    builder  = DocxBuilder()
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
    _sync_exports(db.get_all_jobs(), settings)

    return {"cv_docx": str(cv_docx), "cv_pdf": str(cv_pdf)}


@router.post("/{job_id}/cover-letter", response_model=CoverLetterResponse)
def generate_cover_letter_endpoint(job_id: int, db: Database = Depends(get_db)):
    from generators.cover_letter_pdf import render_cover_letter_pdf
    from services.job_service import _sync_exports
    from utils.cv_contact_parser import parse_contact

    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    settings = get_settings()

    # Parse contact details from the CV (source of truth); fall back to config
    cv_text = settings.cv_path.read_text(encoding="utf-8") if settings.cv_path.exists() else ""
    cv_contact = parse_contact(cv_text)

    person_name    = cv_contact["name"]    or settings.person_name
    person_email   = cv_contact["email"]   or settings.person_email
    person_phone   = cv_contact["phone"]   or settings.person_phone
    person_address = cv_contact["address"] or settings.person_address
    # LinkedIn URL is rarely in the CV text; config is primary, CV URL wins if found
    person_linkedin = cv_contact["linkedin"] or settings.person_linkedin

    try:
        content = application_service.generate_cover_letter(job_id, person_name)
    except Exception as e:
        raise HTTPException(status_code=502, detail=llm_error_message(e))

    # Strip any trailing sign-off the LLM added (Regards / Sincerely / etc.)
    _sign_off_triggers = ("regards,", "sincerely,", "yours truly,", "warm regards,", "kind regards,")
    lines = content.rstrip().splitlines()
    while lines and any(lines[-1].strip().lower().startswith(t) for t in _sign_off_triggers):
        lines.pop()
    while lines and not lines[-1].strip():
        lines.pop()
    if lines and lines[-1].strip() == person_name:
        lines.pop()
    content = "\n".join(lines)

    signed_content = f"{content}\n\nBest regards,\n{person_name}"

    # PDF → outputs/{company}/{person}_coverletter.pdf
    pdf_path = render_cover_letter_pdf(
        signed_content,
        person_name,
        job.company,
        settings.outputs_path,
        person_email=person_email,
        person_phone=person_phone,
        person_address=person_address,
        person_linkedin=person_linkedin,
    )

    # 1. DB blob + path
    db.update_job(
        job_id,
        cover_letter_content=signed_content,
        cover_letter_path=str(pdf_path),
    )

    # 2. Excel sync (cover_letter_content + cover_letter_path columns)
    _sync_exports(db.get_all_jobs(), settings)

    return {"content": signed_content, "docx_path": str(pdf_path)}


@router.get("/{job_id}", response_model=Job)
def get_job(job_id: int, db: Database = Depends(get_db)):
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return job


@router.put("/{job_id}", response_model=Job)
def update_job(job_id: int, req: UpdateJobRequest):
    try:
        return job_service.update_job_status(job_id, req.status, req.notes)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{job_id}/files")
def list_files(job_id: int, db: Database = Depends(get_db)):
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    files = {}
    if job.cv_path and Path(job.cv_path).exists():
        files["cv_docx"] = job.cv_path
        pdf = job.cv_path.replace(".docx", ".pdf")
        if Path(pdf).exists():
            files["cv_pdf"] = pdf
    if job.cover_letter_path and Path(job.cover_letter_path).exists():
        files["cl_docx"] = job.cover_letter_path
        pdf = job.cover_letter_path.replace(".docx", ".pdf")
        if Path(pdf).exists():
            files["cl_pdf"] = pdf
    return files


@router.post("/{job_id}/generate", response_model=GenerateResponse)
def generate(job_id: int, req: GenerateRequest):
    import os
    person_name = os.environ.get("PERSON_NAME", "Applicant")
    cover_letter_content = None
    try:
        if not req.skip_cover_letter:
            cover_letter_content = application_service.generate_cover_letter(job_id, person_name)
        paths = application_service.generate_application(
            job_id, template=req.template, cover_letter_content=cover_letter_content
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=llm_error_message(e))
    return {
        "cv_docx": str(paths.get("cv_docx", "")),
        "cv_pdf": str(paths.get("cv_pdf", "")),
        "cl_docx": str(paths.get("cl_docx", "")) if paths.get("cl_docx") else None,
        "cl_pdf": str(paths.get("cl_pdf", "")) if paths.get("cl_pdf") else None,
    }


@router.post("/{job_id}/interview-prep", response_model=InterviewPrepResponse)
def interview_prep(job_id: int):
    try:
        out_path = interview_service.generate_interview_prep(job_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=llm_error_message(e))
    return {"output_path": str(out_path)}
