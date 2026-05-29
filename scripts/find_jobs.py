#!/usr/bin/env python3
"""Module 1 — Job Discovery. Scrape jobs, score against your CV, export to Excel + Google Sheets."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

import typer
from rich.console import Console
from rich.table import Table

from config import get_settings
from db.models import JobStatus
from services.job_service import find_and_score_jobs, get_jobs

app = typer.Typer(help="Scrape and score job listings.")
console = Console()


@app.command()
def main(
    sources: str = typer.Option("seek", help="Comma-separated: seek, linkedin"),
    location: str = typer.Option("Australia", help="Job location"),
    max_per_source: int = typer.Option(50, help="Max results per source per role"),
    min_score: float = typer.Option(0.0, help="Minimum match score to display"),
    skip_scoring: bool = typer.Option(False, help="Skip Claude scoring (faster, free)"),
    show_all: bool = typer.Option(False, help="Show all jobs from DB, not just new ones"),
) -> None:
    settings = get_settings()
    cv_content = ""
    if not skip_scoring:
        try:
            cv_content = settings.cv_path.read_text(encoding="utf-8").strip()
            if not cv_content:
                console.print("[red]master_cv.md is empty. Run python scripts/setup.py first.[/red]")
                raise typer.Exit(1)
        except FileNotFoundError:
            console.print("[red]data/master_cv.md not found. Run python scripts/setup.py first.[/red]")
            raise typer.Exit(1)

    source_list = [s.strip() for s in sources.split(",") if s.strip()]
    console.print(f"[cyan]Searching:[/cyan] {', '.join(source_list)} | location: {location}")

    jobs = find_and_score_jobs(
        sources=source_list,
        location=location,
        max_per_source=max_per_source,
        cv_content=cv_content,
        skip_scoring=skip_scoring,
    )

    if show_all:
        jobs = get_jobs(min_score=min_score)
    else:
        jobs = [j for j in jobs if j.match_score is None or j.match_score >= min_score]

    if not jobs:
        console.print("[yellow]No jobs found matching criteria.[/yellow]")
        return

    table = Table(title=f"Jobs (sorted by match score)", show_lines=False)
    table.add_column("ID", style="dim", width=5)
    table.add_column("Match %", width=8, justify="right")
    table.add_column("Title", min_width=25)
    table.add_column("Company", min_width=18)
    table.add_column("Location", min_width=12)
    table.add_column("Status", width=10)
    table.add_column("Source", width=10)

    for job in sorted(jobs, key=lambda j: j.match_score or 0, reverse=True):
        score = f"{job.match_score:.0f}" if job.match_score is not None else "—"
        score_style = (
            "green" if (job.match_score or 0) >= 75
            else "yellow" if (job.match_score or 0) >= 50
            else "red"
        )
        table.add_row(
            str(job.id),
            f"[{score_style}]{score}[/{score_style}]",
            job.title,
            job.company,
            job.location or "—",
            job.status.value,
            job.source,
        )

    console.print(table)
    console.print(f"\n[green]✓[/green] {len(jobs)} jobs | jobs/jobs_tracker.xlsx updated")
    console.print("[dim]Next:[/dim] python scripts/generate_application.py <job_id>")


if __name__ == "__main__":
    app()
