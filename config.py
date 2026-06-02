from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT = Path(__file__).parent


class Settings(BaseSettings):
    # LLM
    llm_provider: str = "anthropic"       # anthropic | openai
    llm_model: str = "claude-sonnet-4-6"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 4096
    agent_max_retries: int = 5
    max_job_description_chars: int = 8000

    # Embeddings
    embedding_provider: str = "huggingface"   # huggingface (local/free) | openai
    embedding_model: str = "all-MiniLM-L6-v2"

    # Vector store
    vector_store: str = "chroma"              # chroma | faiss
    vector_store_path: Path = _ROOT / "data" / "vector_store"

    # RAG
    rag_chunk_size: int = 1000
    rag_chunk_overlap: int = 200
    rag_top_k: int = 5
    rag_enabled: bool = True

    # API keys
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # Paths — all overridable via .env
    cv_path: Path = _ROOT / "data" / "master_cv.md"
    target_roles_path: Path = _ROOT / "data" / "target_roles.md"
    cost_log_path: Path = _ROOT / "jobs" / "cost_log.jsonl"
    outputs_path: Path = _ROOT / "outputs"
    resumes_path: Path = _ROOT / "resumes" / "tailored"

    # Output template — set automatically on CV upload; override in .env
    cv_template: str = "professional"

    # API server
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = False

    # CORS — comma-separated: CORS_ORIGINS=http://localhost:3000,http://localhost:5173
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # App
    person_name: str = "Applicant"
    linkedin_li_at_cookie: str = ""
    google_credentials_path: str = ""
    google_sheets_spreadsheet_id: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    model_config = SettingsConfigDict(
        env_file=str(_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Force re-read from .env on next call — useful in tests."""
    global _settings
    _settings = None
