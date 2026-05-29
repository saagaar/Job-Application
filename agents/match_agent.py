from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from rich.progress import Progress, SpinnerColumn, TextColumn

from agents.base_agent import BaseAgent
from config import Settings

SYSTEM_PROMPT = """\
You are a technical recruiter and hiring manager with 15 years of experience in software engineering.

You will be given a job description and a candidate's CV.
Evaluate the match quality and return ONLY a JSON object — no other text, no markdown fences.

Target roles the candidate is pursuing: {target_roles}

Scoring rubric:
- 80-100: Strong match. Most required skills present, title aligns, experience level matches.
- 60-79:  Good match. Core skills align but some gaps. Worth applying.
- 40-59:  Partial match. Transferable skills but significant gaps.
- 0-39:   Weak match. Different domain or seniority level.

Return ONLY this JSON:
{{"score": <int 0-100>, "matching_skills": ["skill1", ...], "gaps": ["gap1", ...], "reasoning": "<2 sentences max>"}}
"""


class MatchAgent(BaseAgent):
    def __init__(
        self,
        llm: BaseChatModel,
        settings: Settings,
        target_roles: list[str] | None = None,
    ) -> None:
        super().__init__(llm, settings)
        self._target_roles = target_roles or []
        roles_str = ", ".join(self._target_roles) or "any software engineering role"
        self._chain = self._build_json_chain(
            SYSTEM_PROMPT.format(target_roles=roles_str)
        )

    def score_job(self, job_description: str, cv_content: str) -> dict:
        result = self._chain.invoke({
            "input": (
                f"## Job Description\n\n{self._truncate(job_description)}"
                f"\n\n## Candidate CV\n\n{cv_content}"
            )
        })
        return {
            "score": float(result.get("score", 0)),
            "matching_skills": result.get("matching_skills", []),
            "gaps": result.get("gaps", []),
            "reasoning": result.get("reasoning", ""),
        }

    def batch_score(self, jobs: list[dict], cv_content: str) -> list[dict]:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            task = progress.add_task(f"Scoring {len(jobs)} jobs...", total=len(jobs))
            for job in jobs:
                try:
                    result = self.score_job(job.get("description", ""), cv_content)
                    job["match_score"] = result["score"]
                    job["_match_details"] = result
                except Exception as e:
                    job["match_score"] = None
                    job["_match_details"] = {"error": str(e)}
                progress.advance(task)
        return jobs
