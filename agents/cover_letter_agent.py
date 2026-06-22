from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from agents.base_agent import BaseAgent
from config import Settings

SYSTEM_PROMPT = """\
You are a senior career coach writing a cover letter for a software engineer.

You will receive:
- The job description
- The candidate's full CV
- Matching skills already identified for this specific role
- Skill gaps if any
- A recruiter's brief analysis of the match quality
- The candidate's personal stories and motivations (optional — may be empty)
- Live company research scraped from the web (optional — may be empty)

Your job: write a cover letter that sounds like a REAL person wrote it.
Curious. Direct. Specific. Human. Not a CV summary. Not corporate filler.

If personal stories are provided, weave 1–2 relevant ones in naturally —
a specific moment or belief says more than any list of skills.

Structure (3 paragraphs, max 400 words):
  1. Opening — what drew you to THIS company and role specifically. If company
     research is provided, use real facts from it (product, mission, recent news).
     Otherwise anchor in the job description. One sentence max about yourself here.
  2. Contribution — 2–3 concrete things you would bring. Ground these in the
     matching skills and actual CV experience. Name real projects, real results,
     real technologies. If a personal story fits naturally here, use it briefly.
  3. Close — one or two sentences max. Say something specific about what you
     want to explore or build together. Do NOT write any of these:
     "I look forward to hearing from you", "I'd appreciate the chance to discuss",
     "I would welcome the opportunity", "Thank you for your consideration".
     End on something that shows you thought about THEIR problem, not yours.

Hard rules:
- Use ONLY information from the job description, CV, and personal stories — never invent
- Do NOT use: "passionate", "team player", "results-driven", "hard worker",
  "I am excited to", "I am a quick learner", "leverage", "synergy", "hit the ground running"
- Do NOT list skills — show them through examples
- Gaps: do not mention unless you can frame as genuine active learning with evidence
- Address the reader directly: "your team", "you are building", "what you are solving"
- Return plain text only — no markdown, no headers, no greeting line, no sign-off
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
        matching_skills: list[str] | None = None,
        gaps: list[str] | None = None,
        reasoning: str = "",
        personal_stories: str = "",
        company_research: str = "",
    ) -> str:
        skills_block    = ", ".join(matching_skills) if matching_skills else "see CV"
        gaps_block      = ", ".join(gaps) if gaps else "none identified"
        stories_block   = personal_stories.strip() or "(none provided)"
        research_block  = company_research.strip() or "(none available)"

        return self._generate_chain.invoke({
            "input": (
                f"## Role\n{job_title} at {company}\n\n"
                f"## Job Description\n{self._truncate(job_description)}\n\n"
                f"## Company Research (use this to show genuine interest)\n{research_block}\n\n"
                f"## Candidate CV\n{cv_content}\n\n"
                f"## Candidate Name\n{person_name}\n\n"
                f"## Matching Skills (highlight these)\n{skills_block}\n\n"
                f"## Skill Gaps (do not fabricate experience for these)\n{gaps_block}\n\n"
                f"## Recruiter Analysis\n{reasoning}\n\n"
                f"## Personal Stories & Motivations\n{stories_block}"
            )
        }).strip()

    def refine(self, draft: str, feedback: str) -> str:
        return self._refine_chain.invoke({
            "input": f"## Current Draft\n{draft}\n\n## Feedback\n{feedback}"
        }).strip()
