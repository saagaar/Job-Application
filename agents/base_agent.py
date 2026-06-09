from __future__ import annotations

import json
import time
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from config import Settings


class CostLoggingCallback(BaseCallbackHandler):
    """Writes token usage to cost_log.jsonl after every LLM response."""

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self._log_path = settings.cost_log_path

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        try:
            usage = response.llm_output or {}
            # Anthropic: {"usage": {"input_tokens": N, "output_tokens": M}}
            input_tokens = usage.get("usage", {}).get("input_tokens", 0)
            output_tokens = usage.get("usage", {}).get("output_tokens", 0)
            # OpenAI: {"token_usage": {"prompt_tokens": N, "completion_tokens": M}}
            if not input_tokens:
                tu = usage.get("token_usage", {})
                input_tokens = tu.get("prompt_tokens", 0)
                output_tokens = tu.get("completion_tokens", 0)
            # Gemini: usage_metadata in the first generation's generation_info
            if not input_tokens and response.generations:
                gen_info = (response.generations[0][0].generation_info or {}) if response.generations[0] else {}
                um = gen_info.get("usage_metadata") or gen_info.get("usageMetadata") or {}
                input_tokens = um.get("prompt_token_count", 0) or um.get("input_tokens", 0)
                output_tokens = um.get("candidates_token_count", 0) or um.get("output_tokens", 0)
            model = usage.get("model") or usage.get("model_name", "unknown")

            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            entry = {
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            with self._log_path.open("a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass


class BaseAgent:
    def __init__(self, llm: BaseChatModel, settings: Settings) -> None:
        self._llm = llm.with_config(callbacks=[CostLoggingCallback(settings)])
        self._settings = settings

    def _build_str_chain(self, system_template: str):
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_template),
            ("human", "{input}"),
        ])
        return (prompt | self._llm | StrOutputParser()).with_retry(
            stop_after_attempt=self._settings.agent_max_retries
        )

    def _build_json_chain(self, system_template: str):
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_template),
            ("human", "{input}"),
        ])
        return (prompt | self._llm | JsonOutputParser()).with_retry(
            stop_after_attempt=self._settings.agent_max_retries
        )

    def _truncate(self, text: str) -> str:
        limit = self._settings.max_job_description_chars
        if len(text) <= limit:
            return text
        return text[:limit] + "\n[... truncated ...]"

    def _load_cv(self) -> str:
        content = self._settings.cv_path.read_text(encoding="utf-8").strip()
        if not content:
            raise ValueError(
                "master_cv.md is empty. Run `python scripts/setup.py` to configure your CV."
            )
        return content
