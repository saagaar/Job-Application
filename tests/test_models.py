"""Pydantic model validation tests."""

import json

import pytest
from pydantic import ValidationError

from db.models import Job, JobStatus


def test_job_status_default() -> None:
    job = Job(
        title="Dev",
        company="X",
        url="https://x.com/1",
        description="desc",
        source="seek",
    )
    assert job.status == JobStatus.NEW


def test_job_date_found_auto_set() -> None:
    job = Job(
        title="Dev",
        company="X",
        url="https://x.com/2",
        description="desc",
        source="seek",
    )
    assert job.date_found is not None


def test_job_status_enum_values() -> None:
    assert JobStatus.NEW.value == "new"
    assert JobStatus.APPLIED.value == "applied"
    assert JobStatus.INTERVIEW.value == "interview"
    assert JobStatus.OFFER.value == "offer"
    assert JobStatus.REJECTED.value == "rejected"


def test_job_model_dump_json_serializable() -> None:
    job = Job(
        title="Dev",
        company="X",
        url="https://x.com/3",
        description="desc",
        source="seek",
        match_score=75.0,
    )
    dumped = job.model_dump(mode="json")
    # Must not raise
    serialized = json.dumps(dumped)
    assert "Dev" in serialized
    assert "75.0" in serialized


def test_job_invalid_status_raises() -> None:
    with pytest.raises(ValidationError):
        Job(
            title="Dev",
            company="X",
            url="https://x.com/4",
            description="desc",
            source="seek",
            status="not_a_real_status",
        )


def test_job_optional_fields_default_none() -> None:
    job = Job(
        title="Dev",
        company="X",
        url="https://x.com/5",
        description="desc",
        source="seek",
    )
    assert job.location is None
    assert job.salary_range is None
    assert job.match_score is None
    assert job.notes is None
    assert job.cv_path is None
    assert job.cover_letter_path is None


def test_job_status_accepts_string_value() -> None:
    job = Job(
        title="Dev",
        company="X",
        url="https://x.com/6",
        description="desc",
        source="seek",
        status="applied",
    )
    assert job.status == JobStatus.APPLIED
