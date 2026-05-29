import sys
from pathlib import Path
from unittest.mock import MagicMock

# Ensure repo root is on sys.path regardless of where pytest is invoked from
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage

from api.deps import get_db
from api.main import app
from config import Settings, reset_settings
from db.database import Database
from db.models import Job, JobStatus


@pytest.fixture(autouse=True)
def _reset_settings():
    """Reset the Settings singleton between tests so patches take effect."""
    reset_settings()
    yield
    reset_settings()


@pytest.fixture
def tmp_db(tmp_path: Path) -> Database:
    """Real SQLite DB in a pytest-managed temp directory — no mocking."""
    db = Database(tmp_path / "test_jobs.db")
    db.init_schema()
    return db


@pytest.fixture
def mock_settings(tmp_path: Path) -> Settings:
    """Settings instance with safe defaults for tests — no real API keys needed."""
    cv_file = tmp_path / "cv.md"
    cv_file.write_text("# Test CV\n\nExperienced engineer.")
    return Settings(
        llm_provider="anthropic",
        anthropic_api_key="test-key",
        person_name="Test User",
        rag_enabled=False,
        vector_store_path=tmp_path / "vs",
        cv_path=cv_file,
        cost_log_path=tmp_path / "cost_log.jsonl",
    )


@pytest.fixture
def mock_llm() -> BaseChatModel:
    """Mock LangChain BaseChatModel — never calls a real API."""
    llm = MagicMock(spec=BaseChatModel)
    llm.invoke.return_value = AIMessage(content="mock response")
    llm.with_config.return_value = llm
    llm.with_retry.return_value = llm
    # Make __or__ work so prompt | llm | parser chains don't crash
    llm.__or__ = MagicMock(return_value=llm)
    return llm


@pytest.fixture
def sample_job() -> Job:
    return Job(
        title="Senior Backend Engineer",
        company="Acme Corp",
        url="https://acme.com/jobs/1",
        description="We need an experienced Python backend engineer.",
        source="seek",
        location="Sydney",
        match_score=82.0,
    )


@pytest.fixture
def seeded_db(tmp_db: Database, sample_job: Job) -> tuple[Database, int]:
    """DB with one job pre-inserted. Returns (db, job_id)."""
    job_id = tmp_db.insert_job(sample_job)
    return tmp_db, job_id


@pytest.fixture
def client(tmp_db: Database):
    """TestClient with DB dependency overridden to the temp DB."""
    app.dependency_overrides[get_db] = lambda: tmp_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def seeded_client(seeded_db):
    """TestClient backed by a DB with one job already inserted."""
    db, job_id = seeded_db
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c, job_id
    app.dependency_overrides.clear()
