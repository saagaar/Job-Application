from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    NEW = "new"
    APPLIED = "applied"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"


class Job(BaseModel):
    id: Optional[int] = None
    title: str
    company: str
    url: str
    description: str
    source: str  # "linkedin" | "seek" | "company_page" | "manual"
    location: Optional[str] = None
    salary_range: Optional[str] = None
    # default_factory ensures date is set at creation time even when not provided
    date_found: Optional[datetime] = Field(default_factory=datetime.utcnow)
    match_score: Optional[float] = None
    status: JobStatus = JobStatus.NEW
    notes: Optional[str] = None
    applied_date: Optional[datetime] = None
    cv_path: Optional[str] = None
    cover_letter_path: Optional[str] = None

    model_config = {"from_attributes": True}
