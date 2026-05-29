from __future__ import annotations

from langchain_core.vectorstores import VectorStore, VectorStoreRetriever

from config import Settings


def create_retriever(vector_store: VectorStore, settings: Settings) -> VectorStoreRetriever:
    return vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={"k": settings.rag_top_k},
    )
