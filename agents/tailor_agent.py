from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from agents.base_agent import BaseAgent
from config import Settings

SYSTEM_PROMPT = """\
You are an expert CV writer. You will tailor a candidate's master CV for a specific job application.

STRICT RULES:
1. NEVER fabricate experience, skills, dates, companies, or qualifications.
2. You MAY: reorder bullet points, adjust emphasis, rewrite the professional summary, highlight relevant skills.
3. Keep all factual information (dates, companies, titles) exactly as in the source CV.
4. The summary must be 3-4 sentences max, tailored to the target role.
5. Return ONLY valid JSON — no markdown fences, no explanation.

Schema:
{{
  "summary": "string",
  "experience": [
    {{"title": "string", "company": "string", "dates": "string", "location": "string", "bullets": ["string"]}}
  ],
  "skills": {{
    "languages": ["string"],
    "frameworks": ["string"],
    "databases": ["string"],
    "cloud_infra": ["string"],
    "tools": ["string"],
    "other": ["string"]
  }},
  "education": [
    {{"degree": "string", "institution": "string", "year": "string", "notes": "string"}}
  ],
  "tailoring_notes": "string"
}}
"""


class TailorAgent(BaseAgent):
    def __init__(self, llm: BaseChatModel, settings: Settings) -> None:
        super().__init__(llm, settings)
        self._chain = self._build_json_chain(SYSTEM_PROMPT)

    def tailor_cv(
        self,
        job_description: str,
        cv_content: str,
        company: str,
        job_title: str,
    ) -> dict:
        return self._chain.invoke({
            "input": (
                f"## Target Role\n{job_title} at {company}\n\n"
                f"## Job Description\n{self._truncate(job_description)}\n\n"
                f"## Candidate's Master CV\n{cv_content}"
            )
        })
