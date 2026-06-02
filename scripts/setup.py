#!/usr/bin/env python3
"""First-run setup wizard. Run once before using any other scripts."""

import os
import subprocess
import sys
from pathlib import Path

# Allow running from any directory
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

console = Console()

ROOT = Path(__file__).parent.parent
ENV_PATH = ROOT / ".env"
CV_PATH = ROOT / "data" / "master_cv.md"


def load_dotenv_file() -> dict[str, str]:
    env: dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


def save_env(env: dict[str, str]) -> None:
    lines = [f"{k}={v}" for k, v in env.items()]
    ENV_PATH.write_text("\n".join(lines) + "\n")


def ensure_directories() -> None:
    dirs = [
        ROOT / "jobs",
        ROOT / "outputs" / "cover_letters",
        ROOT / "resumes" / "tailored",
        ROOT / "data",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)


def check_anthropic_key(api_key: str) -> bool:
    try:
        import anthropic
        from config import get_settings
        client = anthropic.Anthropic(api_key=api_key)
        client.messages.create(
            model=get_settings().llm_model,
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}],
        )
        return True
    except Exception as e:
        console.print(f"[red]API key test failed:[/red] {e}")
        return False


def main() -> None:
    console.print(Panel.fit(
        "[bold cyan]Job Seeker Assistant — Setup[/bold cyan]\n"
        "This wizard configures your environment, initialises the database,\n"
        "and verifies your API keys.",
        border_style="cyan",
    ))

    env = load_dotenv_file()
    changed = False

    # --- ANTHROPIC_API_KEY ---
    if not env.get("ANTHROPIC_API_KEY"):
        key = Prompt.ask("[yellow]Enter your Anthropic API key[/yellow]", password=True)
        env["ANTHROPIC_API_KEY"] = key
        changed = True

    console.print("[dim]Testing Anthropic API key...[/dim]", end=" ")
    if check_anthropic_key(env["ANTHROPIC_API_KEY"]):
        console.print("[green]✓[/green]")
    else:
        console.print("[red]✗[/red]")
        new_key = Prompt.ask("Enter a valid Anthropic API key", password=True)
        env["ANTHROPIC_API_KEY"] = new_key
        changed = True

    # --- PERSON_NAME ---
    if not env.get("PERSON_NAME"):
        name = Prompt.ask("[yellow]Your full name[/yellow] (used in CV/cover letter file names)")
        env["PERSON_NAME"] = name
        changed = True
    else:
        console.print(f"[dim]Name:[/dim] {env['PERSON_NAME']}")

    # --- GOOGLE SHEETS (optional) ---
    if not env.get("GOOGLE_SHEETS_SPREADSHEET_ID"):
        if Confirm.ask("[dim]Configure Google Sheets sync?[/dim] (optional)", default=False):
            env["GOOGLE_CREDENTIALS_PATH"] = Prompt.ask("Path to Google Service Account JSON key file")
            env["GOOGLE_SHEETS_SPREADSHEET_ID"] = Prompt.ask("Google Sheet ID (from the URL)")
            changed = True

    # --- LINKEDIN (optional) ---
    if not env.get("LINKEDIN_LI_AT_COOKIE"):
        if Confirm.ask("[dim]Add LinkedIn li_at cookie for authenticated scraping?[/dim] (optional, see README)", default=False):
            console.print("[dim]To get your li_at cookie: log into LinkedIn → DevTools → Application → Cookies → li_at[/dim]")
            env["LINKEDIN_LI_AT_COOKIE"] = Prompt.ask("li_at cookie value", password=True)
            changed = True

    if changed:
        save_env(env)
        console.print("[green]✓[/green] .env saved")

    # --- DIRECTORIES ---
    ensure_directories()
    console.print("[green]✓[/green] Directories verified")

    # --- DATABASE ---
    os.environ["ANTHROPIC_API_KEY"] = env["ANTHROPIC_API_KEY"]
    from db.database import Database
    db = Database()
    db.init_schema()
    console.print("[green]✓[/green] Database initialised at jobs/jobs.db")

    # --- MASTER CV ---
    cv_content = CV_PATH.read_text(encoding="utf-8").strip() if CV_PATH.exists() else ""
    if not cv_content:
        console.print(Panel(
            "[bold yellow]Action required:[/bold yellow] data/master_cv.md is empty.\n\n"
            "Fill it with your CV in Markdown format. See the plan for the expected structure.\n"
            "All AI features depend on this file.",
            border_style="yellow",
        ))
        if Confirm.ask("Open data/master_cv.md in your default editor now?", default=True):
            editor = os.environ.get("EDITOR", "open")
            subprocess.run([editor, str(CV_PATH)])
    else:
        console.print(f"[green]✓[/green] master_cv.md present ({len(cv_content)} chars)")

    console.print(Panel.fit(
        "[bold green]Setup complete![/bold green]\n\n"
        "Next steps:\n"
        "  1. Fill in [bold]data/master_cv.md[/bold] if not done\n"
        "  2. Run [bold]python scripts/find_jobs.py --sources seek --max 10[/bold]\n"
        "  3. Run [bold]python scripts/generate_application.py <job_id>[/bold]",
        border_style="green",
    ))


if __name__ == "__main__":
    main()
