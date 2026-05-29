from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from config import Settings


def create_llm(settings: Settings) -> BaseChatModel:
    """Return a configured BaseChatModel for the provider named in settings.

    OCP: add a new provider by adding one `if` block here — nothing else changes.
    """
    if settings.llm_provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=settings.llm_model,
            api_key=settings.anthropic_api_key,
            max_tokens=settings.llm_max_tokens,
            temperature=settings.llm_temperature,
        )

    if settings.llm_provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.openai_api_key,
            max_tokens=settings.llm_max_tokens,
            temperature=settings.llm_temperature,
        )

    raise ValueError(
        f"Unknown LLM_PROVIDER: {settings.llm_provider!r}. "
        f"Supported: anthropic, openai"
    )
