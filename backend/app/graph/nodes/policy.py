
"""LangGraph node for retrieving and interpreting payer PA policies."""

from langchain_core.prompts import ChatPromptTemplate

from app.graph.state import CaseState, PolicyResult
from app.graph.nodes._trace import traced
from app.llm.client import STRONG_MODEL, get_llm
from app.rag.retriever import retrieve_policy_chunks


POLICY_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
You are a payer-policy interpretation assistant.

Use only the supplied policy excerpts to determine whether
prior authorization (PA) is required.

Rules:
- Do not invent policy requirements.
- Do not infer a rule that the excerpts do not establish.
- Distinguish explicit requirements from unclear information.
- If the excerpts conflict, return status="conflict".
- If evidence is insufficient, return status="low_confidence".
- If no relevant policy establishes the requirement, return
  status="not_found".
- Return status="found" only when the evidence supports a conclusion.
- Set pa_required to true or false only when supported by evidence.
- Cite only document, page, and section metadata from the excerpts.
- Never approve or deny a prescription or predict approval.
- Return the requested structured output.
            """,
        ),
        (
            "human",
            """
Prescription drug: {drug}
NDC: {ndc}
Plan ID: {plan_id}

Retrieved policy excerpts:
{context}

Interpret the policy for this prescription.
            """,
        ),
    ]
)


def _manual_review(message: str) -> dict:
    """Return a safe state update when policy evidence is insufficient."""
    return {
        "policy": PolicyResult(
            status="low_confidence",
            pa_required=None,
            reasons=[message],
            citations=[],
        ),
        "status": "needs_manual_review",
        "errors": [message],
    }


def _metadata_value(metadata: dict, *keys: str):
    """Read the first available metadata field."""
    for key in keys:
        value = metadata.get(key)
        if value is not None:
            return value
    return None


@traced("policy")
def policy_node(state: CaseState) -> dict:
    """Retrieve payer policy and interpret its PA requirements."""

    rx = state.get("rx")
    coverage = state.get("coverage")

    if rx is None or coverage is None:
        return _manual_review(
            "Prescription or coverage information is unavailable."
        )

    if coverage.status != "active":
        return _manual_review(
            "Active coverage is required before evaluating payer policy."
        )

    if not rx.drug and not rx.ndc:
        return _manual_review(
            "Drug name and NDC are missing; policy cannot be identified."
        )

    try:
        # Retrieve policy chunks using drug and plan information.
        documents = retrieve_policy_chunks(
            drug=rx.drug,
            ndc=rx.ndc,
            plan_id=coverage.plan_id,
        )

        if not documents:
            return {
                "policy": PolicyResult(
                    status="not_found",
                    pa_required=None,
                    reasons=["No relevant payer policy was retrieved."],
                    citations=[],
                ),
                "status": "needs_manual_review",
            }

        # Build context and an allowlist of citation metadata.
        excerpts = []
        allowed_citations = set()

        for document in documents:
            metadata = document.metadata or {}

            document_name = _metadata_value(
                metadata, "document", "source"
            )
            page = metadata.get("page")
            section = metadata.get("section")

            if document_name is not None and page is not None:
                try:
                    page = int(page)
                    # The ingestion pipeline should store 1-based pages.
                    if page < 1:
                        continue
                except (TypeError, ValueError):
                    continue

                citation = {
                    "document": str(document_name),
                    "page": page,
                    "section": str(section or "Unspecified"),
                }
                allowed_citations.add(
                    (
                        citation["document"],
                        citation["page"],
                        citation["section"],
                    )
                )

                excerpts.append(
                    f"Document: {citation['document']}\n"
                    f"Page: {citation['page']}\n"
                    f"Section: {citation['section']}\n"
                    f"Text:\n{document.page_content}"
                )

        if not excerpts:
            return _manual_review(
                "Retrieved policy excerpts lack valid citation metadata."
            )

        # Ask the LLM to return a structured PolicyResult.
        llm = get_llm(STRONG_MODEL)
        structured_llm = llm.with_structured_output(PolicyResult)
        chain = POLICY_PROMPT | structured_llm

        result = chain.invoke(
            {
                "drug": rx.drug or "Not provided",
                "ndc": rx.ndc or "Not provided",
                "plan_id": coverage.plan_id or "Not provided",
                "context": "\n\n---\n\n".join(excerpts),
            }
        )

        if not isinstance(result, PolicyResult):
            result = PolicyResult.model_validate(result)

        # Never accept citations that do not match retrieved evidence.
        for citation in result.citations:
            key = (
                citation.document,
                citation.page,
                citation.section,
            )
            if key not in allowed_citations:
                return _manual_review(
                    "Policy interpretation returned an unverified citation."
                )

        # A definitive answer requires evidence and at least one citation.
        if (
            result.status != "found"
            or result.pa_required is None
            or not result.citations
        ):
            result.pa_required = None
            return {
                "policy": result,
                "status": "needs_manual_review",
            }

        return {"policy": result}

    except Exception:
        # Log a safe error category through your logging infrastructure.
        # Do not log prescription payloads, policy text, or secrets.
        return _manual_review(
            "Policy retrieval or interpretation failed; manual review is required."
        )
