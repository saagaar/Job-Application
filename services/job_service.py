from __future__ import annotations

from pathlib import Path
from typing import Optional

from config import Settings, get_settings
from db.database import Database
from db.excel_export import ExcelExporter
from db.models import Job, JobStatus
from db.sheets_sync import SheetsSync
from providers.llm_factory import create_llm


def _load_target_roles(settings: Settings) -> list[str]:
    if not settings.target_roles_path.exists():
        return []
    lines = settings.target_roles_path.read_text(encoding="utf-8").splitlines()
    return [l.lstrip("-• ").strip() for l in lines if l.strip()]


def find_and_score_jobs(
    sources: list[str],
    location: str,
    max_per_source: int,
    cv_content: str,
    skip_scoring: bool = False,
    settings: Settings | None = None,
) -> list[Job]:
    from agents.match_agent import MatchAgent

    settings = settings or get_settings()
    db = Database()
    target_roles = _load_target_roles(settings)
    all_new: list[Job] = []

    for source in sources:
        scraper_jobs = _run_scraper(source, target_roles, location, max_per_source, settings)
        new_count = 0
        for raw in scraper_jobs:
            job = Job(
                title=raw["title"],
                company=raw["company"],
                url=raw["url"],
                description=raw.get("description", ""),
                source=raw["source"],
                location=raw.get("location"),
                salary_range=raw.get("salary_range"),
            )
            inserted_id = db.insert_job(job)
            if inserted_id:
                job.id = inserted_id
                all_new.append(job)
                new_count += 1
        db.log_scrape_run(source, len(scraper_jobs), new_count)

    if not skip_scoring and all_new:
        llm = create_llm(settings)
        agent = MatchAgent(llm, settings, target_roles)
        unscored = db.get_unscored_jobs()
        raw_list = [{"id": j.id, "description": j.description} for j in unscored]
        agent.batch_score(raw_list, cv_content)
        for item in raw_list:
            if item.get("match_score") is not None:
                db.update_job(item["id"], match_score=item["match_score"])

    jobs = db.get_all_jobs()
    _sync_exports(jobs, settings)
    return jobs


def get_jobs(
    status: Optional[JobStatus] = None,
    min_score: float = 0.0,
) -> list[Job]:
    return Database().get_all_jobs(status=status, min_score=min_score)


def update_job_status(
    job_id: int,
    status: JobStatus,
    notes: Optional[str] = None,
    settings: Settings | None = None,
) -> Job:
    settings = settings or get_settings()
    db = Database()
    kwargs: dict = {"status": status}
    if notes is not None:
        kwargs["notes"] = notes
    db.update_job(job_id, **kwargs)
    jobs = db.get_all_jobs()
    _sync_exports(jobs, settings)
    job = db.get_job(job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found")
    return job


def _run_scraper(
    source: str,
    roles: list[str],
    location: str,
    max_per_source: int,
    settings: Settings,
) -> list[dict]:
    results: list[dict] = []
    if source == "seek":
        from scrapers.seek_scraper import SeekScraper
        scraper = SeekScraper()
        for role in roles:
            results.extend(scraper.search(role, location, max_per_source))
    elif source == "linkedin":
        from scrapers.linkedin_scraper import LinkedInScraper
        scraper = LinkedInScraper(li_at_cookie=settings.linkedin_li_at_cookie or None)
        for role in roles:
            results.extend(scraper.search(role, location, max_per_source))
    return results


def _sync_exports(jobs: list[Job], settings: Settings) -> None:
    ExcelExporter().export(jobs)
    if settings.google_sheets_spreadsheet_id and settings.google_credentials_path:
        try:
            SheetsSync(
                settings.google_sheets_spreadsheet_id,
                settings.google_credentials_path,
            ).push_jobs(jobs)
        except Exception as e:
            from rich.console import Console
            Console().print(f"[yellow]Google Sheets sync failed:[/yellow] {e}")
