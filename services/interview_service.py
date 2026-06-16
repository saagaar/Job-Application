from __future__ import annotations

from pathlib import Path

from config import Settings, get_settings
from db.database import Database


def generate_interview_prep(
    job_id: int,
    settings: Settings | None = None,
) -> Path:
    from agents.interview_agent import InterviewAgent
    from providers.embedding_factory import create_embeddings
    from providers.llm_factory import create_llm
    from providers.vectorstore_factory import create_vector_store
    from rag.indexer import DocumentIndexer
    from rag.retriever import create_retriever

    settings = settings or get_settings()
    db = Database()
    job = db.get_job(job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found.")

    # Prefer tailored CV if already generated
    cv_content = ""
    if job.cv_path and Path(job.cv_path).exists():
        try:
            from docx import Document
            doc = Document(job.cv_path)
            cv_content = "\n".join(p.text for p in doc.paragraphs)
        except Exception:
            pass
    if not cv_content:
        cv_content = settings.cv_path.read_text(encoding="utf-8").strip()
    if not cv_content:
        raise ValueError("No CV content found. Fill data/master_cv.md first.")

    _interview_provider = settings.interview_llm_provider or settings.cv_llm_provider
    _interview_model = settings.interview_llm_model or settings.cv_llm_model
    llm = create_llm(settings, provider=_interview_provider, model=_interview_model)

    # Set up RAG: index CV + job description, then retrieve context
    embeddings = create_embeddings(settings)
    vs = create_vector_store(embeddings, settings)
    indexer = DocumentIndexer(vs, settings)
    indexer.index_cv()
    indexer.index_job(
        job_id=job.id or 0,
        title=job.title,
        company=job.company,
        description=job.description,
        url=job.url,
    )
    retriever = create_retriever(vs, settings)

    agent = InterviewAgent(llm, settings, retriever)
    prep = agent.generate_prep(job.description, cv_content, job.company, job.title)
    markdown = agent.format_as_markdown(prep, job.company, job.title)

    safe_company = job.company.replace(" ", "_").replace("/", "-")
    out_dir = settings.outputs_path / safe_company
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"interview_prep_{safe_company}.md"
    out_path.write_text(markdown, encoding="utf-8")
    return out_path
