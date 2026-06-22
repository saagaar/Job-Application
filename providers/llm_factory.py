from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from config import Settings


def llm_error_message(exc: Exception) -> str:
    """Return a concise, user-facing message from an LLM provider exception.

    Provider errors (Gemini 429, Anthropic auth, OpenAI rate-limit, etc.) embed
    their human-readable text in the first line of str(exc). We grab that and
    trim it so the API response stays readable.
    """
    first_line = str(exc).split("\n")[0].strip()
    return first_line[:400] if len(first_line) > 400 else first_line


def create_llm(
    settings: Settings,
    provider: str = "",
    model: str = "",
) -> BaseChatModel:
    """Return a configured BaseChatModel for the active provider.

    OCP: add a new provider by adding one `if` block here — nothing else changes.

    provider/model override the settings values when supplied, allowing
    different agents to use different models (e.g. Gemini for scoring,
    Claude for writing). Falls back to settings.llm_provider/llm_model.

    Supported providers (set LLM_PROVIDER in .env):
        cloud:  anthropic | openai | gemini
        local:  ollama
    """
    _provider = provider or settings.llm_provider
    _model = model or settings.llm_model

    if _provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=_model,
            api_key=settings.anthropic_api_key,
            max_tokens=settings.llm_max_tokens,
            temperature=settings.llm_temperature,
        )

    if _provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=_model,
            api_key=settings.openai_api_key,
            max_tokens=settings.llm_max_tokens,
            temperature=settings.llm_temperature,
        )

    if _provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=_model,
            google_api_key=settings.gemini_api_key,
            max_output_tokens=settings.llm_max_tokens,
            temperature=settings.llm_temperature,
            transport="rest",  # avoid gRPC/SSL issues on macOS
            thinking_budget=0
        )

    if _provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=_model,
            base_url=settings.ollama_base_url,
            temperature=settings.llm_temperature,
            # Ollama does not accept max_tokens; use num_predict instead
            num_predict=settings.llm_max_tokens,
        )

    raise ValueError(
        f"Unknown LLM provider: {_provider!r}. "
        f"Supported: anthropic, openai, gemini, ollama"
    )
