#!/usr/bin/env python3
"""Module 3 — Generate interview preparation for a shortlisted job."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

import subprocess

import typer
from rich.console import Console
from rich.panel import Panel

from db.database import Database
from services.interview_service import generate_interview_prep

app = typer.Typer(help="Generate interview questions, answers, and skill gap resources.")
console = Console()


@app.command()
def main(
    job_id: int = typer.Argument(..., help="Job ID from the database"),
    open_file: bool = typer.Option(True, help="Open the output file after generation"),
) -> None:
    db = Database()
    job = db.get_job(job_id)
    if not job:
        console.print(f"[red]Job {job_id} not found.[/red]")
        raise typer.Exit(1)

    console.print(Panel(
        f"[bold]{job.title}[/bold] at [cyan]{job.company}[/cyan]",
        title="Generating interview prep",
        border_style="cyan",
    ))
    console.print("[dim]Asking Claude to generate interview questions...[/dim]")

    out_path = generate_interview_prep(job_id)

    console.print(f"[green]✓[/green] Saved to: [dim]{out_path}[/dim]")

    if open_file:
        try:
            subprocess.run(["open", str(out_path)], check=False)
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    app()
