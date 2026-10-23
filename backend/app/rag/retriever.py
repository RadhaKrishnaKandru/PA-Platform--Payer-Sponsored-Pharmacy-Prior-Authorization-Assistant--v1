"""Policy retriever stub. Replaced by the Chroma-backed retriever on the RAG step."""

from typing import Any


def retrieve_policy_chunks(
    *,
    drug: str | None = None,
    ndc: str | None = None,
    plan_id: str | None = None,
) -> list[Any]:
    """Return policy chunks for a drug and plan.

    Stub: returns no chunks, so policy_node reports "no relevant policy
    retrieved" and routes the case to manual review.
    """
    return []