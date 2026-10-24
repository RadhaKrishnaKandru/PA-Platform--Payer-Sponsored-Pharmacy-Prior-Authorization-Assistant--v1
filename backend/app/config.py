"""Application settings loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Settings for local services and external integrations."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    groq_api_key: SecretStr | None = None
    fast_model: str = "openai/gpt-oss-20b"
    strong_model: str = "openai/gpt-oss-120b"
    postgres_url: SecretStr | None = None
    mongo_url: str | None = None
    chroma_dir: Path = Path("data/chroma")
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    rag_top_k: int = Field(default=3, ge=1)
    rag_min_score: float = Field(default=0.25, ge=0.0, le=1.0)
    policies_dir: Path = Path("data/policies")
    chroma_collection: str = "policies"


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
