#!/usr/bin/env python3
"""Module 2 — Generate tailored CV and cover letter for a job."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from db.database import Database
from services.application_service import (
    generate_application,
    generate_cover_letter,
    refine_cover_letter,
)

app = typer.Typer(help="Generate tailored CV and cover letter for a job listing.")
console = Console()


@app.command()
def main(
    job_id: int = typer.Argument(..., help="Job ID from the database (see find_jobs output)"),
    template: str = typer.Option("professional", help="CV template name"),
    skip_cover_letter: bool = typer.Option(False, help="Skip cover letter generation"),
    no_interactive: bool = typer.Option(False, help="Skip cover letter refinement prompt"),
) -> None:
    db = Database()
    job = db.get_job(job_id)
    if not job:
        console.print(f"[red]Job {job_id} not found. Run find_jobs.py to populate the database.[/red]")
        raise typer.Exit(1)

    person_name = os.environ.get("PERSON_NAME", "Applicant")

    console.print(Panel(
        f"[bold]{job.title}[/bold] at [cyan]{job.company}[/cyan]\n"
        f"Match: [green]{job.match_score:.0f}%[/green]  |  Source: {job.source}  |  Location: {job.location or '—'}"
        if job.match_score else
        f"[bold]{job.title}[/bold] at [cyan]{job.company}[/cyan]",
        title="Generating application",
        border_style="cyan",
    ))

    # Tailoring CV
    console.print("[dim]Tailoring CV with Claude...[/dim]")

    cover_letter_content = None
    if not skip_cover_letter:
        console.print("[dim]Generating cover letter...[/dim]")
        draft = generate_cover_letter(job_id, person_name)

        console.print(Panel(draft, title="Cover Letter Draft", border_style="dim"))

        if not no_interactive:
            while True:
                action = Prompt.ask(
                    "Cover letter action",
                    choices=["approve", "refine", "skip"],
                    default="approve",
                )
                if action == "approve":
                    cover_letter_content = draft
                    break
                elif action == "skip":
                    cover_letter_content = None
                    break
                elif action == "refine":
                    feedback = Prompt.ask("What should be changed?")
                    draft = refine_cover_letter(draft, feedback)
                    console.print(Panel(draft, title="Revised Cover Letter", border_style="dim"))
        else:
            cover_letter_content = draft

    paths = generate_application(job_id, template=template, cover_letter_content=cover_letter_content)

    console.print(Panel(
        "\n".join(f"[green]✓[/green] {label}: [dim]{path}[/dim]" for label, path in {
            "CV (DOCX)": paths.get("cv_docx"),
            "CV (PDF)": paths.get("cv_pdf"),
            "Cover Letter (DOCX)": paths.get("cl_docx"),
            "Cover Letter (PDF)": paths.get("cl_pdf"),
        }.items() if path),
        title="Files generated",
        border_style="green",
    ))

    console.print(f"\n[dim]Next:[/dim] python scripts/interview_prep.py {job_id}")


if __name__ == "__main__":
    app()
