from __future__ import annotations

from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStore

from config import Settings


def create_vector_store(embeddings: Embeddings, settings: Settings) -> VectorStore:
    """Return a configured VectorStore for the backend named in settings."""
    settings.vector_store_path.mkdir(parents=True, exist_ok=True)

    if settings.vector_store == "chroma":
        from langchain_chroma import Chroma
        return Chroma(
            persist_directory=str(settings.vector_store_path),
            embedding_function=embeddings,
        )

    if settings.vector_store == "faiss":
        from langchain_community.vectorstores import FAISS
        index_path = settings.vector_store_path / "faiss_index"
        if index_path.exists():
            return FAISS.load_local(
                str(index_path),
                embeddings,
                allow_dangerous_deserialization=True,
            )
        store = FAISS.from_texts([""], embeddings)
        store.save_local(str(index_path))
        return store

    raise ValueError(
        f"Unknown VECTOR_STORE: {settings.vector_store!r}. "
        f"Supported: chroma, faiss"
    )
