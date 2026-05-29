from __future__ import annotations

from typing import Optional
from pydantic import BaseModel
from db.models import Job, JobStatus


class JobListResponse(BaseModel):
    jobs: list[Job]
    total: int


class ScrapeRequest(BaseModel):
    sources: list[str] = ["seek"]
    location: str = "Australia"
    max_per_source: int = 50
    skip_scoring: bool = False


class ScrapeResponse(BaseModel):
    jobs_found: int
    jobs_new: int


class UpdateJobRequest(BaseModel):
    status: Optional[JobStatus] = None
    notes: Optional[str] = None


class GenerateRequest(BaseModel):
    template: str = "professional"
    skip_cover_letter: bool = False


class GenerateResponse(BaseModel):
    cv_docx: str
    cv_pdf: str
    cl_docx: Optional[str] = None
    cl_pdf: Optional[str] = None


class InterviewPrepResponse(BaseModel):
    output_path: str
