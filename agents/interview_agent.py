from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langchain_core.vectorstores import VectorStoreRetriever

from agents.rag_agent import RAGAgent
from config import Settings

SYSTEM_PROMPT = """\
You are an expert interview coach with deep knowledge of software engineering hiring.

Given a job description, a candidate CV, and any retrieved context about the company or role,
generate comprehensive interview preparation materials.

Return ONLY valid JSON — no markdown fences, no extra text.

Schema:
{{
  "behavioral_questions": [
    {{
      "question": "string",
      "suggested_answer": "string (2-3 sentences using STAR framework)",
      "star_tip": "string (one sentence hint on which STAR element to emphasize)"
    }}
  ],
  "technical_questions": [
    {{
      "question": "string",
      "suggested_answer": "string",
      "depth": "surface | moderate | deep"
    }}
  ],
  "skill_gaps": [
    {{
      "skill": "string",
      "gap_explanation": "string",
      "resources": [
        {{"title": "string", "type": "course | book | docs | practice", "url": "string or empty"}}
      ]
    }}
  ],
  "questions_to_ask": ["string"],
  "company_insights": "string (2-3 bullet points about the company/role)"
}}

Include 5-8 behavioral questions, 5-8 technical questions, up to 5 skill gaps, and 5 questions to ask.
"""


class InterviewAgent(RAGAgent):
    def __init__(
        self,
        llm: BaseChatModel,
        settings: Settings,
        retriever: VectorStoreRetriever,
    ) -> None:
        super().__init__(llm, settings, retriever)
        self._chain = self._build_rag_json_chain(SYSTEM_PROMPT)

    def generate_prep(
        self,
        job_description: str,
        cv_content: str,
        company: str,
        job_title: str,
    ) -> dict:
        question = (
            f"## Role\n{job_title} at {company}\n\n"
            f"## Job Description\n{self._truncate(job_description)}\n\n"
            f"## Candidate CV\n{cv_content}"
        )
        return self._chain.invoke(question)

    def format_as_markdown(self, prep: dict, company: str, job_title: str) -> str:
        lines = [f"# Interview Prep: {job_title} at {company}\n"]

        if prep.get("company_insights"):
            lines += ["## Company & Role Insights\n", prep["company_insights"], ""]

        if prep.get("behavioral_questions"):
            lines.append("## Behavioral Questions\n")
            for i, q in enumerate(prep["behavioral_questions"], 1):
                lines += [
                    f"### {i}. {q['question']}",
                    f"**Suggested answer:** {q['suggested_answer']}",
                    f"*STAR tip: {q.get('star_tip', '')}*",
                    "",
                ]

        if prep.get("technical_questions"):
            lines.append("## Technical Questions\n")
            for i, q in enumerate(prep["technical_questions"], 1):
                lines += [
                    f"### {i}. {q['question']} `[{q.get('depth', '')}]`",
                    f"**Suggested answer:** {q['suggested_answer']}",
                    "",
                ]

        if prep.get("skill_gaps"):
            lines.append("## Skill Gaps & Learning Resources\n")
            for gap in prep["skill_gaps"]:
                lines += [f"### {gap['skill']}", gap.get("gap_explanation", "")]
                for r in gap.get("resources", []):
                    url = r.get("url", "")
                    link = f"[{r['title']}]({url})" if url else r["title"]
                    lines.append(f"- {link} *({r.get('type', '')})*")
                lines.append("")

        if prep.get("questions_to_ask"):
            lines.append("## Questions to Ask the Interviewer\n")
            for q in prep["questions_to_ask"]:
                lines.append(f"- {q}")
            lines.append("")

        return "\n".join(lines)
