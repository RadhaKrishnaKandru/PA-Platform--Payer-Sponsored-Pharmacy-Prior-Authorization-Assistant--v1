"""Local embedding model configuration for policy retrieval."""

from functools import lru_cache

from langchain_huggingface import HuggingFaceEmbeddings

from app.config import get_settings


@lru_cache
def get_embeddings() -> HuggingFaceEmbeddings:
    """Return the cached local embedding model."""
    settings = get_settings()
    return HuggingFaceEmbeddings(
        model_name=settings.embedding_model,
        model_kwargs={"local_files_only": True},
        encode_kwargs={"normalize_embeddings": True},
    )
