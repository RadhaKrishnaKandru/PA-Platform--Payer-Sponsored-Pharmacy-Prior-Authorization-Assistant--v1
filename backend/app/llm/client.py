from functools import lru_cache

from langchain_groq import ChatGroq

from app.config import get_settings


FAST_MODEL = get_settings().fast_model
STRONG_MODEL = get_settings().strong_model


@lru_cache(maxsize=None)
def get_llm(
    model: str = FAST_MODEL,
    temperature: float = 0,
) -> ChatGroq:
    """Create or return the cached Groq chat model for these settings."""
    settings = get_settings()
    if settings.groq_api_key is None:
        raise RuntimeError("GROQ_API_KEY is not set. Add it to backend/.env.")

    return ChatGroq(
        model=model,
        temperature=temperature,
        reasoning_format="parsed",
        api_key=settings.groq_api_key.get_secret_value(),
        max_retries=4,
    )