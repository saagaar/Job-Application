from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from db.models import Job, JobStatus

DB_PATH = Path(__file__).parent.parent / "jobs" / "jobs.db"

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS jobs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    title               TEXT    NOT NULL,
    company             TEXT    NOT NULL,
    url                 TEXT    NOT NULL UNIQUE,
    description         TEXT    NOT NULL,
    source              TEXT    NOT NULL,
    location            TEXT,
    salary_range        TEXT,
    date_found          TEXT    NOT NULL,
    match_score         REAL,
    match_skills        TEXT,
    match_gaps          TEXT,
    match_reasoning     TEXT,
    status              TEXT    NOT NULL DEFAULT 'new',
    notes               TEXT,
    applied_date        TEXT,
    cv_path               TEXT,
    cover_letter_path     TEXT,
    cover_letter_content  TEXT
)
"""

CREATE_SCRAPE_RUNS = """
CREATE TABLE IF NOT EXISTS scrape_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT    NOT NULL,
    source      TEXT    NOT NULL,
    jobs_found  INTEGER NOT NULL,
    jobs_new    INTEGER NOT NULL
)
"""


def _row_to_job(row: sqlite3.Row) -> Job:
    d = dict(row)
    for field in ("date_found", "applied_date"):
        if d.get(field):
            d[field] = datetime.fromisoformat(d[field])
    return Job(**d)


class Database:
    def __init__(self, db_path: Path = DB_PATH):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(CREATE_TABLE)
            conn.execute(CREATE_SCRAPE_RUNS)
            for col in ("match_skills", "match_gaps", "match_reasoning", "cover_letter_content"):
                try:
                    conn.execute(f"ALTER TABLE jobs ADD COLUMN {col} TEXT")
                except Exception:
                    pass  # column already exists

    def insert_job(self, job: Job) -> Optional[int]:
        sql = """
        INSERT OR IGNORE INTO jobs
            (title, company, url, description, source, location, salary_range,
             date_found, match_score, status, notes)
        VALUES
            (:title, :company, :url, :description, :source, :location, :salary_range,
             :date_found, :match_score, :status, :notes)
        """
        data = job.model_dump()
        data["date_found"] = data["date_found"].isoformat() if data["date_found"] else datetime.utcnow().isoformat()
        data["status"] = data["status"].value if isinstance(data["status"], JobStatus) else data["status"]
        with self._connect() as conn:
            cur = conn.execute(sql, data)
            return cur.lastrowid if cur.lastrowid else None

    def update_job(self, job_id: int, **kwargs) -> None:
        if not kwargs:
            return
        for k, v in kwargs.items():
            if isinstance(v, JobStatus):
                kwargs[k] = v.value
            elif isinstance(v, datetime):
                kwargs[k] = v.isoformat()
        sets = ", ".join(f"{k} = :{k}" for k in kwargs)
        kwargs["_id"] = job_id
        with self._connect() as conn:
            conn.execute(f"UPDATE jobs SET {sets} WHERE id = :_id", kwargs)

    def get_job(self, job_id: int) -> Optional[Job]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return _row_to_job(row) if row else None

    def get_all_jobs(
        self,
        status: Optional[JobStatus] = None,
        min_score: float = 0.0,
    ) -> list[Job]:
        sql = "SELECT * FROM jobs WHERE 1=1"
        params: list = []
        if status:
            sql += " AND status = ?"
            params.append(status.value)
        if min_score > 0:
            sql += " AND (match_score IS NULL OR match_score >= ?)"
            params.append(min_score)
        sql += " ORDER BY match_score DESC NULLS LAST"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_row_to_job(r) for r in rows]

    def get_unscored_jobs(self) -> list[Job]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE match_score IS NULL"
            ).fetchall()
        return [_row_to_job(r) for r in rows]

    def search_jobs(self, query: str) -> list[Job]:
        pattern = f"%{query}%"
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE title LIKE ? OR company LIKE ? OR description LIKE ?",
                (pattern, pattern, pattern),
            ).fetchall()
        return [_row_to_job(r) for r in rows]

    def mark_as_applied(self, job_id: int, cv_path: str, cover_letter_path: str) -> None:
        self.update_job(
            job_id,
            status=JobStatus.APPLIED,
            applied_date=datetime.utcnow(),
            cv_path=cv_path,
            cover_letter_path=cover_letter_path,
        )

    def log_scrape_run(self, source: str, jobs_found: int, jobs_new: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO scrape_runs (timestamp, source, jobs_found, jobs_new) VALUES (?, ?, ?, ?)",
                (datetime.utcnow().isoformat(), source, jobs_found, jobs_new),
            )
