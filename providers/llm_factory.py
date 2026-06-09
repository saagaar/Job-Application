from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from config import Settings


def create_llm(settings: Settings) -> BaseChatModel:
    """Return a configured BaseChatModel for the provider named in settings.

    OCP: add a new provider by adding one `if` block here — nothing else changes.

    Supported providers (set LLM_PROVIDER in .env):
        cloud:  anthropic | openai | gemini
        local:  ollama
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

    if settings.llm_provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=settings.llm_model,
            google_api_key=settings.gemini_api_key,
            max_output_tokens=settings.llm_max_tokens,
            temperature=settings.llm_temperature,
        )

    if settings.llm_provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=settings.llm_model,
            base_url=settings.ollama_base_url,
            temperature=settings.llm_temperature,
            # Ollama does not accept max_tokens; use num_predict instead
            num_predict=settings.llm_max_tokens,
        )

    raise ValueError(
        f"Unknown LLM_PROVIDER: {settings.llm_provider!r}. "
        f"Supported: anthropic, openai, gemini, ollama"
    )
