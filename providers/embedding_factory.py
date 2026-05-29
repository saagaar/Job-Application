from __future__ import annotations

from langchain_core.embeddings import Embeddings

from config import Settings


def create_embeddings(settings: Settings) -> Embeddings:
    """Return a configured Embeddings instance for the provider named in settings."""
    if settings.embedding_provider == "huggingface":
        from langchain_huggingface import HuggingFaceEmbeddings
        return HuggingFaceEmbeddings(model_name=settings.embedding_model)

    if settings.embedding_provider == "openai":
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(
            model=settings.embedding_model,
            api_key=settings.openai_api_key,
        )

    raise ValueError(
        f"Unknown EMBEDDING_PROVIDER: {settings.embedding_provider!r}. "
        f"Supported: huggingface, openai"
    )
