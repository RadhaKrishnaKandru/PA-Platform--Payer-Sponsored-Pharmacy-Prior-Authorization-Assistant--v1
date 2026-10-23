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
    return ChatGroq(
        model=model,
        temperature=temperature,
        reasoning_format="parsed",
        api_key=get_settings().groq_api_key,
        max_retries=4,
    )