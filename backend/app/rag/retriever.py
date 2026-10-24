"""Chroma-backed retrieval for synthetic payer policy documents."""

import logging
import re
from typing import Literal

from langchain_chroma import Chroma
from langchain_core.documents import Document

from app.config import get_settings
from app.rag.embeddings import get_embeddings

logger = logging.getLogger(__name__)


def _drug_names(metadata_value: object) -> set[str]:
    """Normalize the supported list and delimited-string metadata formats."""
    if isinstance(metadata_value, list):
        values = metadata_value
    elif isinstance(metadata_value, str):
        values = re.split(r"[|;,]", metadata_value)
    else:
        values = []
    return {value.strip().casefold() for value in values if isinstance(value, str)}


def _metadata_filter(
    *,
    plan_id: str | None,
    document_names: list[str] | None = None,
    section: str | None = None,
) -> dict[str, object] | None:
    """Build a Chroma metadata filter from the available constraints."""
    conditions: dict[str, object] = {}
    if plan_id:
        conditions["plan_id"] = plan_id
    if document_names is not None:
        if not document_names:
            return None
        conditions["document"] = {"$in": document_names}
    if section:
        conditions["section"] = section
    if len(conditions) > 1:
        return {"$and": [{key: value} for key, value in conditions.items()]}
    return conditions or None


def retrieve_policy_chunks(
    *,
    drug: str | None = None,
    ndc: str | None = None,
    plan_id: str | None = None,
    focus: Literal["policy", "documentation"] = "policy",
) -> list[Document]:
    """Retrieve relevant, cited policy chunks from the persistent Chroma index."""
    settings = get_settings()
    if not settings.chroma_dir.exists():
        return []

    drug_name = drug.strip().casefold() if drug and drug.strip() else None
    if drug and not drug_name:
        return []
    if not drug_name and not ndc and not plan_id:
        return []

    try:
        vector_store = Chroma(
            collection_name=settings.chroma_collection,
            persist_directory=str(settings.chroma_dir),
            embedding_function=get_embeddings(),
        )
        filters = _metadata_filter(plan_id=plan_id)
        indexed = vector_store.get(where=filters) if filters else vector_store.get()
        metadatas = indexed.get("metadatas") or []
        if not metadatas:
            return []

        document_names: list[str] | None = None
        if drug_name:
            document_names = sorted(
                {
                    str(metadata["document"])
                    for metadata in metadatas
                    if metadata
                    and metadata.get("document")
                    and drug_name in _drug_names(metadata.get("drugs"))
                }
            )
            if not document_names:
                return []

        base_filter = _metadata_filter(
            plan_id=plan_id,
            document_names=document_names,
        )
        if focus == "documentation":
            documentation_filter = _metadata_filter(
                plan_id=plan_id,
                document_names=document_names,
                section="Required Documentation",
            )
            if documentation_filter:
                indexed_documentation = vector_store.get(
                    where=documentation_filter,
                    include=["documents", "metadatas"],
                )
                documentation_documents = indexed_documentation.get("documents") or []
                documentation_metadatas = (
                    indexed_documentation.get("metadatas") or []
                )
                documentation_chunks = [
                    Document(page_content=content[:900], metadata=dict(metadata))
                    for content, metadata in zip(
                        documentation_documents,
                        documentation_metadatas,
                    )
                    if content is not None
                    and metadata
                    and metadata.get("section") == "Required Documentation"
                ]
                documentation_chunks.sort(
                    key=lambda document: (
                        int(document.metadata.get("page", 0)),
                        int(document.metadata.get("chunk_index", 0)),
                    )
                )
                if documentation_chunks:
                    return documentation_chunks

        query = " ".join(
            part.strip()
            for part in (drug, ndc, plan_id)
            if part and part.strip()
        )
        if not query:
            return []

        top_k = settings.rag_top_k
        policy_results = vector_store.similarity_search_with_relevance_scores(
            query,
            k=top_k,
            filter=base_filter,
        )
        return [
            Document(
                page_content=document.page_content[:900],
                metadata=dict(document.metadata),
            )
            for document, score in policy_results
            if score >= settings.rag_min_score
        ][:top_k]
    except Exception as exc:
        logger.warning("Policy retrieval unavailable (%s)", type(exc).__name__)
        return []
