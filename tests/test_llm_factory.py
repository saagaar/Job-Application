"""Unit tests for providers/llm_factory.py.

Provider classes are mocked so no real API calls are made.
Each test verifies that create_llm() instantiates the right class
with the right parameters for a given LLM_PROVIDER setting.
"""

from unittest.mock import MagicMock, patch

import pytest

from config import Settings


def _settings(**kwargs) -> Settings:
    """Build a minimal Settings object with safe test defaults."""
    base = dict(
        llm_temperature=0.1,
        llm_max_tokens=512,
        rag_enabled=False,
    )
    base.update(kwargs)
    return Settings(**base)


# ── Anthropic ─────────────────────────────────────────────────────────────────

def test_anthropic_creates_chat_anthropic():
    mock_cls = MagicMock()
    with patch("providers.llm_factory.ChatAnthropic", mock_cls, create=True):
        # Patch the lazy import inside the function
        with patch.dict("sys.modules", {"langchain_anthropic": MagicMock(ChatAnthropic=mock_cls)}):
            from providers.llm_factory import create_llm
            settings = _settings(
                llm_provider="anthropic",
                llm_model="claude-haiku-4-5-20251001",
                anthropic_api_key="test-ant-key",
            )
            create_llm(settings)
    mock_cls.assert_called_once_with(
        model="claude-haiku-4-5-20251001",
        api_key="test-ant-key",
        max_tokens=512,
        temperature=0.1,
    )


# ── OpenAI ────────────────────────────────────────────────────────────────────

def test_openai_creates_chat_openai():
    mock_cls = MagicMock()
    with patch.dict("sys.modules", {"langchain_openai": MagicMock(ChatOpenAI=mock_cls)}):
        from providers.llm_factory import create_llm
        settings = _settings(
            llm_provider="openai",
            llm_model="gpt-4o-mini",
            openai_api_key="test-oai-key",
        )
        create_llm(settings)
    mock_cls.assert_called_once_with(
        model="gpt-4o-mini",
        api_key="test-oai-key",
        max_tokens=512,
        temperature=0.1,
    )


# ── Gemini ────────────────────────────────────────────────────────────────────

def test_gemini_creates_google_genai():
    mock_cls = MagicMock()
    with patch.dict("sys.modules", {
        "langchain_google_genai": MagicMock(ChatGoogleGenerativeAI=mock_cls)
    }):
        from providers.llm_factory import create_llm
        settings = _settings(
            llm_provider="gemini",
            llm_model="gemini-1.5-flash",
            gemini_api_key="test-gemini-key",
        )
        create_llm(settings)
    mock_cls.assert_called_once_with(
        model="gemini-1.5-flash",
        google_api_key="test-gemini-key",
        max_output_tokens=512,
        temperature=0.1,
    )


# ── Ollama ────────────────────────────────────────────────────────────────────

def test_ollama_creates_chat_ollama():
    mock_cls = MagicMock()
    with patch.dict("sys.modules", {"langchain_ollama": MagicMock(ChatOllama=mock_cls)}):
        from providers.llm_factory import create_llm
        settings = _settings(
            llm_provider="ollama",
            llm_model="llama3.2",
            ollama_base_url="http://localhost:11434",
        )
        create_llm(settings)
    mock_cls.assert_called_once_with(
        model="llama3.2",
        base_url="http://localhost:11434",
        temperature=0.1,
        num_predict=512,
    )


# ── Unknown provider ──────────────────────────────────────────────────────────

def test_unknown_provider_raises():
    from providers.llm_factory import create_llm
    settings = _settings(llm_provider="unknown_provider")
    with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
        create_llm(settings)
