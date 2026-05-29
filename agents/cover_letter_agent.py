from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from agents.base_agent import BaseAgent
from config import Settings

SYSTEM_PROMPT = """\
You are an expert career coach writing a professional cover letter.

Structure: 3 paragraphs
  1. Hook + why this specific company and role
  2. 2-3 specific contributions you'd make, grounded in the candidate's actual experience
  3. Confident, forward-looking close

Rules:
- Max 350 words
- Avoid clichés: "passionate", "team player", "hard worker", "results-driven"
- Sound human and direct, not corporate
- Never fabricate experience not in the CV
- Return plain text only — no markdown, no headers, no subject line
"""

REFINE_SYSTEM = """\
You are editing a cover letter draft based on feedback.
Apply the feedback precisely. Keep the same structure unless told otherwise.
Return the full revised cover letter as plain text only.
"""


class CoverLetterAgent(BaseAgent):
    def __init__(self, llm: BaseChatModel, settings: Settings) -> None:
        super().__init__(llm, settings)
        self._generate_chain = self._build_str_chain(SYSTEM_PROMPT)
        self._refine_chain = self._build_str_chain(REFINE_SYSTEM)

    def generate(
        self,
        job_description: str,
        cv_content: str,
        company: str,
        job_title: str,
        person_name: str,
    ) -> str:
        return self._generate_chain.invoke({
            "input": (
                f"## Role\n{job_title} at {company}\n\n"
                f"## Job Description\n{self._truncate(job_description)}\n\n"
                f"## Candidate CV\n{cv_content}\n\n"
                f"## Candidate Name\n{person_name}"
            )
        }).strip()

    def refine(self, draft: str, feedback: str) -> str:
        return self._refine_chain.invoke({
            "input": f"## Current Draft\n{draft}\n\n## Feedback\n{feedback}"
        }).strip()
