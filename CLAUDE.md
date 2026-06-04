# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## First-time setup

```bash
python scripts/setup.py          # interactive wizard: validates API keys, creates dirs, seeds DB
```

Required: a `.env` file (copy `.env.example`) with at least one LLM provider key and `PERSON_NAME` set.  
Required: `data/master_cv.md` populated with the user's CV in Markdown — all AI features depend on it.

## Running the API server

```bash
python -m uvicorn api.main:app --reload --port 8000
# or via the entry point:
python api/main.py
```

Health check: `GET /health`. Interactive docs: `http://localhost:8000/docs`.

## CLI scripts

```bash
python scripts/find_jobs.py --sources seek,linkedin --location "Australia" --max 20
python scripts/generate_application.py <job_id>
python scripts/interview_prep.py <job_id>
```

## Tests

```bash
pytest                            # all tests
pytest tests/test_api.py          # single file
pytest tests/test_api.py::test_list_jobs   # single test
pytest -x                         # stop on first failure
```

Tests use a real in-memory SQLite DB (`tmp_db` fixture) — never mock the database. The `mock_llm` fixture in `conftest.py` prevents real API calls.

## Architecture

### Request flow (API)

```
HTTP request
  → api/routers/{jobs,cv}.py      (FastAPI router)
  → services/{job,application,interview,cv}_service.py   (orchestration)
  → agents/*.py                   (LLM chains)
  → db/database.py                (SQLite via raw SQL)
```

### LLM layer

All agents inherit `BaseAgent` (`agents/base_agent.py`), which provides:
- `_build_str_chain(system_template)` → LangChain chain returning plain text
- `_build_json_chain(system_template)` → chain returning parsed JSON dict
- `_truncate(text)` → clips text to `max_job_description_chars` (default 8000)
- `_load_cv()` → reads `data/master_cv.md`
- `CostLoggingCallback` → appends token usage to `jobs/cost_log.jsonl`

LLM instantiation is entirely in `providers/llm_factory.py:create_llm()`. To add a new provider, add one `if` block there — nothing else changes. Active provider is set via `LLM_PROVIDER` in `.env`.

### Agents

| Agent | Purpose |
|---|---|
| `MatchAgent` | Scores jobs 0–100 against CV; `batch_score(jobs, cv_content)` mutates each job dict with `match_score` and `_match_details` |
| `TailorAgent` | Returns JSON with tailored CV sections (summary, experience, skills) for a specific job |
| `CoverLetterAgent` | Returns Markdown cover letter text |
| `InterviewAgent` | Generates interview prep document using RAG context |
| `RagAgent` | Base for RAG-enabled agents; injects retrieved chunks into the prompt |

### RAG pipeline

Used only for interview prep. `rag/indexer.py` indexes CV + job description into a Chroma (or FAISS) vector store at `data/vector_store/`. `rag/retriever.py` fetches top-k chunks. Re-indexes on every request (no caching).

### Document generation

`generators/docx_builder.py` builds the DOCX from a template dict.  
`generators/template_engine.py` + `templates/cv_template_*.py` define the CV layout.  
`generators/pdf_renderer.py` converts DOCX → PDF.  
Output files land in `resumes/tailored/` (CVs) and `outputs/cover_letters/`.

### Database

Single SQLite file at `jobs/jobs.db`. All access via `db/database.py:Database`. Schema: `jobs` + `scrape_runs` tables. Jobs are deduplicated by URL (`INSERT OR IGNORE`). `get_unscored_jobs()` is the entry point before batch scoring.

### Chrome extension

`chrome-extension/content.js` — class-free scraping approach (LinkedIn's CSS classes change on every deploy):
- **Title**: `meta[property="og:title"]` content, company suffix stripped
- **Company**: `document.title` regex (`"Title at Company | LinkedIn"`), fallback to `a[href*="/company/"]`
- **Description**: all `<p>` tag text joined — structured job content without UI noise
- **Job URL**: normalised to `https://www.linkedin.com/jobs/view/{id}/` regardless of source URL format (`?currentJobId=` or `/jobs/view/` path)

Saved jobs sync to the API via `POST /api/jobs/import`.

### Configuration

All settings live in `config.py:Settings` (Pydantic `BaseSettings`). Every field is overridable via `.env`. Use `get_settings()` everywhere — it's a singleton. In tests, call `reset_settings()` (or use the `_reset_settings` autouse fixture) to clear the singleton between tests.

### Key data files (gitignored, user-managed)

- `data/master_cv.md` — user's full CV in Markdown; source of truth for all AI personalisation
- `data/target_roles.md` — role titles and seniority the user is targeting; injected into match scoring prompt
- `data/skills_matrix.md` — skills breakdown; referenced by tailor and cover letter agents
