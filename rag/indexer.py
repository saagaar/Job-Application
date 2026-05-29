from __future__ import annotations

from pathlib import Path

from langchain_core.vectorstores import VectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import Settings


class DocumentIndexer:
    """Chunks text documents and upserts them into the vector store."""

    def __init__(self, vector_store: VectorStore, settings: Settings) -> None:
        self._vs = vector_store
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.rag_chunk_size,
            chunk_overlap=settings.rag_chunk_overlap,
            length_function=len,
        )
        self._settings = settings

    def index_text(self, text: str, metadata: dict) -> None:
        if not text.strip():
            return
        docs = self._splitter.create_documents([text], metadatas=[metadata])
        self._vs.add_documents(docs)

    def index_cv(self) -> None:
        text = self._settings.cv_path.read_text(encoding="utf-8").strip()
        self.index_text(text, {"source": "master_cv", "type": "cv"})

    def index_job(self, job_id: int, title: str, company: str, description: str, url: str = "") -> None:
        text = f"Job: {title} at {company}\n\n{description}"
        self.index_text(text, {
            "source": url or f"job_{job_id}",
            "type": "job",
            "company": company,
            "job_id": str(job_id),
        })

    def index_file(self, path: Path, metadata: dict) -> None:
        text = path.read_text(encoding="utf-8").strip()
        self.index_text(text, metadata)
