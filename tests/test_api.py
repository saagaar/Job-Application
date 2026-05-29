"""FastAPI route tests.

DB dependency is overridden via app.dependency_overrides (see conftest.py).
Service layer functions (Claude API, scrapers, file generation) are mocked
with pytest-mock so tests never touch the network or filesystem.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from db.models import Job, JobStatus


# ── Health ─────────────────────────────────────────────────────────────────────

def test_health(client) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ── GET /api/jobs ──────────────────────────────────────────────────────────────

def test_list_jobs_empty(client, mocker) -> None:
    mocker.patch("api.routers.jobs.job_service.get_jobs", return_value=[])
    resp = client.get("/api/jobs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["jobs"] == []


def test_list_jobs_returns_seeded_jobs(client, mocker, sample_job) -> None:
    mocker.patch("api.routers.jobs.job_service.get_jobs", return_value=[sample_job])
    resp = client.get("/api/jobs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["jobs"][0]["title"] == sample_job.title


def test_list_jobs_filter_by_status(client, mocker, sample_job) -> None:
    applied = sample_job.model_copy(update={"status": JobStatus.APPLIED})
    mocker.patch("api.routers.jobs.job_service.get_jobs", return_value=[applied])
    resp = client.get("/api/jobs", params={"status": "applied"})
    assert resp.status_code == 200
    assert resp.json()["jobs"][0]["status"] == "applied"


# ── GET /api/jobs/{id} ─────────────────────────────────────────────────────────

def test_get_job_found(seeded_client) -> None:
    client, job_id = seeded_client
    resp = client.get(f"/api/jobs/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["company"] == "Acme Corp"


def test_get_job_not_found(client) -> None:
    resp = client.get("/api/jobs/99999")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


# ── PUT /api/jobs/{id} ─────────────────────────────────────────────────────────

def test_update_job_status(seeded_client, mocker) -> None:
    client, job_id = seeded_client

    updated = Job(
        id=job_id,
        title="Senior Backend Engineer",
        company="Acme Corp",
        url="https://acme.com/jobs/1",
        description="desc",
        source="seek",
        status=JobStatus.APPLIED,
    )
    mocker.patch("api.routers.jobs.job_service.update_job_status", return_value=updated)

    resp = client.put(f"/api/jobs/{job_id}", json={"status": "applied"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "applied"


def test_update_job_not_found(client, mocker) -> None:
    mocker.patch(
        "api.routers.jobs.job_service.update_job_status",
        side_effect=ValueError("Job 99999 not found"),
    )
    resp = client.put("/api/jobs/99999", json={"status": "rejected"})
    assert resp.status_code == 404


# ── GET /api/jobs/{id}/files ───────────────────────────────────────────────────

def test_list_files_no_files(seeded_client) -> None:
    client, job_id = seeded_client
    resp = client.get(f"/api/jobs/{job_id}/files")
    assert resp.status_code == 200
    assert resp.json() == {}


def test_list_files_job_not_found(client) -> None:
    resp = client.get("/api/jobs/99999/files")
    assert resp.status_code == 404


# ── POST /api/jobs/scrape ──────────────────────────────────────────────────────

def test_scrape_jobs_skip_scoring(client, mocker) -> None:
    mocker.patch("api.routers.jobs.job_service.get_jobs", return_value=[])
    mocker.patch("api.routers.jobs.job_service.find_and_score_jobs", return_value=[])
    resp = client.post("/api/jobs/scrape", json={"sources": ["seek"], "skip_scoring": True})
    assert resp.status_code == 200
    data = resp.json()
    assert "jobs_found" in data
    assert "jobs_new" in data


def test_scrape_jobs_requires_cv_when_scoring(client, mocker, tmp_path) -> None:
    # Patch get_settings() in the router to return settings with an empty CV path
    empty_cv = tmp_path / "empty_cv.md"
    empty_cv.write_text("")

    from config import Settings
    fake_settings = Settings(
        anthropic_api_key="test",
        cv_path=empty_cv,
        cost_log_path=tmp_path / "log.jsonl",
        vector_store_path=tmp_path / "vs",
    )
    mocker.patch("api.routers.jobs.get_settings", return_value=fake_settings)

    resp = client.post("/api/jobs/scrape", json={"sources": ["seek"], "skip_scoring": False})
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"].lower()


# ── POST /api/jobs/{id}/generate ──────────────────────────────────────────────

def test_generate_application(seeded_client, mocker) -> None:
    client, job_id = seeded_client

    mocker.patch(
        "api.routers.jobs.application_service.generate_cover_letter",
        return_value="Dear Hiring Manager...",
    )
    mocker.patch(
        "api.routers.jobs.application_service.generate_application",
        return_value={
            "cv_docx": Path("/tmp/CV_Test_Acme.docx"),
            "cv_pdf": Path("/tmp/CV_Test_Acme.pdf"),
            "cl_docx": Path("/tmp/CL_Test_Acme.docx"),
            "cl_pdf": Path("/tmp/CL_Test_Acme.pdf"),
        },
    )

    resp = client.post(f"/api/jobs/{job_id}/generate", json={"template": "professional"})
    assert resp.status_code == 200
    data = resp.json()
    assert "cv_docx" in data
    assert "cv_pdf" in data


def test_generate_application_job_not_found(client, mocker) -> None:
    mocker.patch(
        "api.routers.jobs.application_service.generate_cover_letter",
        return_value="Dear...",
    )
    mocker.patch(
        "api.routers.jobs.application_service.generate_application",
        side_effect=ValueError("Job 99999 not found in database."),
    )
    resp = client.post("/api/jobs/99999/generate", json={"skip_cover_letter": True})
    assert resp.status_code == 400


# ── POST /api/jobs/{id}/interview-prep ────────────────────────────────────────

def test_interview_prep(seeded_client, mocker) -> None:
    client, job_id = seeded_client
    mocker.patch(
        "api.routers.jobs.interview_service.generate_interview_prep",
        return_value=Path("/tmp/outputs/Acme_Corp/interview_prep_Acme_Corp.md"),
    )
    resp = client.post(f"/api/jobs/{job_id}/interview-prep")
    assert resp.status_code == 200
    assert "output_path" in resp.json()


def test_interview_prep_job_not_found(client, mocker) -> None:
    mocker.patch(
        "api.routers.jobs.interview_service.generate_interview_prep",
        side_effect=ValueError("Job 99999 not found."),
    )
    resp = client.post("/api/jobs/99999/interview-prep")
    assert resp.status_code == 400
