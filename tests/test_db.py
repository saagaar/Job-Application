"""Database CRUD tests — uses a real SQLite temp file, no mocks."""

import pytest

from db.database import Database
from db.models import Job, JobStatus


def make_job(url: str = "https://example.com/jobs/1", **kwargs) -> Job:
    defaults = dict(
        title="Backend Engineer",
        company="TestCo",
        url=url,
        description="A job description.",
        source="seek",
    )
    defaults.update(kwargs)
    return Job(**defaults)


# ── Schema ─────────────────────────────────────────────────────────────────────

def test_init_schema_idempotent(tmp_db: Database) -> None:
    """Calling init_schema twice must not raise (CREATE TABLE IF NOT EXISTS)."""
    tmp_db.init_schema()  # second call


# ── Insert ─────────────────────────────────────────────────────────────────────

def test_insert_job_returns_id(tmp_db: Database) -> None:
    job_id = tmp_db.insert_job(make_job())
    assert isinstance(job_id, int)
    assert job_id >= 1


def test_insert_duplicate_url_ignored(tmp_db: Database) -> None:
    url = "https://example.com/jobs/dup"
    first = tmp_db.insert_job(make_job(url=url))
    second = tmp_db.insert_job(make_job(url=url, title="Different Title"))
    assert first is not None
    assert second is None  # INSERT OR IGNORE — duplicate silently skipped


# ── Get ────────────────────────────────────────────────────────────────────────

def test_get_job_found(tmp_db: Database) -> None:
    job_id = tmp_db.insert_job(make_job(title="Python Dev"))
    job = tmp_db.get_job(job_id)
    assert job is not None
    assert job.title == "Python Dev"
    assert job.id == job_id


def test_get_job_not_found(tmp_db: Database) -> None:
    assert tmp_db.get_job(99999) is None


# ── Update ─────────────────────────────────────────────────────────────────────

def test_update_job_score(tmp_db: Database) -> None:
    job_id = tmp_db.insert_job(make_job())
    tmp_db.update_job(job_id, match_score=91.5)
    job = tmp_db.get_job(job_id)
    assert job.match_score == 91.5


def test_update_job_notes(tmp_db: Database) -> None:
    job_id = tmp_db.insert_job(make_job())
    tmp_db.update_job(job_id, notes="Looks promising")
    assert tmp_db.get_job(job_id).notes == "Looks promising"


# ── Get all ────────────────────────────────────────────────────────────────────

def test_get_all_jobs_sorted_by_score(tmp_db: Database) -> None:
    tmp_db.insert_job(make_job(url="https://a.com/1", match_score=50.0))
    tmp_db.insert_job(make_job(url="https://a.com/2", match_score=90.0))
    tmp_db.insert_job(make_job(url="https://a.com/3", match_score=70.0))
    jobs = tmp_db.get_all_jobs()
    scores = [j.match_score for j in jobs if j.match_score is not None]
    assert scores == sorted(scores, reverse=True)


def test_get_all_jobs_filter_by_status(tmp_db: Database) -> None:
    id1 = tmp_db.insert_job(make_job(url="https://a.com/4"))
    id2 = tmp_db.insert_job(make_job(url="https://a.com/5"))
    tmp_db.update_job(id1, status=JobStatus.APPLIED)

    applied = tmp_db.get_all_jobs(status=JobStatus.APPLIED)
    assert len(applied) == 1
    assert applied[0].id == id1

    new_jobs = tmp_db.get_all_jobs(status=JobStatus.NEW)
    assert any(j.id == id2 for j in new_jobs)


# ── Unscored ───────────────────────────────────────────────────────────────────

def test_get_unscored_jobs(tmp_db: Database) -> None:
    tmp_db.insert_job(make_job(url="https://a.com/6"))
    tmp_db.insert_job(make_job(url="https://a.com/7", match_score=75.0))
    unscored = tmp_db.get_unscored_jobs()
    assert all(j.match_score is None for j in unscored)
    assert len(unscored) == 1


# ── Mark as applied ────────────────────────────────────────────────────────────

def test_mark_as_applied(tmp_db: Database) -> None:
    job_id = tmp_db.insert_job(make_job())
    tmp_db.mark_as_applied(job_id, "/path/cv.docx", "/path/cl.docx")
    job = tmp_db.get_job(job_id)
    assert job.status == JobStatus.APPLIED
    assert job.applied_date is not None
    assert job.cv_path == "/path/cv.docx"
    assert job.cover_letter_path == "/path/cl.docx"


# ── Search ─────────────────────────────────────────────────────────────────────

def test_search_jobs_by_title(tmp_db: Database) -> None:
    tmp_db.insert_job(make_job(url="https://a.com/8", title="Python Developer"))
    tmp_db.insert_job(make_job(url="https://a.com/9", title="Java Engineer"))
    results = tmp_db.search_jobs("Python")
    assert len(results) == 1
    assert "Python" in results[0].title


def test_search_jobs_by_company(tmp_db: Database) -> None:
    tmp_db.insert_job(make_job(url="https://a.com/10", company="Acme Inc"))
    results = tmp_db.search_jobs("Acme")
    assert len(results) == 1


def test_search_jobs_no_match(tmp_db: Database) -> None:
    tmp_db.insert_job(make_job(url="https://a.com/11"))
    assert tmp_db.search_jobs("xyznomatch") == []


# ── Scrape run log ─────────────────────────────────────────────────────────────

def test_log_scrape_run(tmp_db: Database) -> None:
    tmp_db.log_scrape_run("seek", jobs_found=10, jobs_new=5)
    # No assertion needed — just verify it doesn't raise
