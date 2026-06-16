from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_db
from config import get_settings
from api.schemas import (
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
    if not req.skip_cover_letter:
        cover_letter_content = application_service.generate_cover_letter(job_id, person_name)
    try:
        paths = application_service.generate_application(
            job_id, template=req.template, cover_letter_content=cover_letter_content
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
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
    return {"output_path": str(out_path)}
