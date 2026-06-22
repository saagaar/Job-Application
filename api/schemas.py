from __future__ import annotations

from typing import Optional
from pydantic import BaseModel
from db.models import Job, JobStatus


class CVUploadResponse(BaseModel):
    message: str
    chars: int


class CVContentResponse(BaseModel):
    content: str
    chars: int


class ImportJobItem(BaseModel):
    title: str
    company: str
    url: str
    location: str = ""
    description: str = ""
    source: str = "extension"


class ImportRequest(BaseModel):
    jobs: list[ImportJobItem]
    score: bool = True


class ImportResponse(BaseModel):
    imported: int
    skipped: int
    scored: int


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


class ScoreResponse(BaseModel):
    scored: int
    failed: int
    error: str = ""


class SingleJobScoreResponse(BaseModel):
    job_id: int
    score: float
    matching_skills: list[str]
    gaps: list[str]
    reasoning: str


class CoverLetterResponse(BaseModel):
    content: str
    docx_path: str


class CVGenerateResponse(BaseModel):
    cv_docx: str
    cv_pdf: str
