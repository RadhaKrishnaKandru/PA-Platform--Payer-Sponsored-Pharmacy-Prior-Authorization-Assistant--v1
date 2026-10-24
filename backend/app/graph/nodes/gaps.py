
"""LangGraph node for identifying missing PA documentation."""

from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate

from app.graph.state import CaseState, MissingItem
from app.graph.nodes._trace import traced
from app.llm.client import FAST_MODEL, get_llm
from app.rag.retriever import retrieve_policy_chunks


class GapAnalysis(BaseModel):
    """Structured output for missing-documentation analysis."""

    missing_items: list[MissingItem] = Field(default_factory=list)


GAPS_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
You are a payer-policy documentation analysis assistant.

Identify documentation or clinical information explicitly required
by the supplied payer policy that is not present in the submitted case.

Rules:
- Use only the supplied policy excerpts to establish requirements.
- Compare policy requirements against the submitted information.
- Do not assume a document is missing if its availability is unknown.
- Do not invent clinical facts or documentation requirements.
- Do not recommend medications or alternatives.
- Do not predict approval or denial.
- Each missing item must explain why the policy requires it.
- If no missing items are supported by the evidence, return an empty list.
- Return the requested structured output.
            """,
        ),
        (
            "human",
            """
Drug: {drug}
NDC: {ndc}
Plan ID: {plan_id}

Submitted prescription information:
{prescription}

Documents reported as submitted:
{submitted_documents}

Relevant payer policy excerpts:
{policy_context}

Identify the documentation gaps supported by this evidence.
            """,
        ),
    ]
)


@traced("gaps")
def gaps_node(state: CaseState) -> dict:
    """Compare submitted case information with payer documentation rules."""

    rx = state.get("rx")
    coverage = state.get("coverage")
    policy = state.get("policy")

    # This node should run only when PA is known to be required.
    if (
        rx is None
        or coverage is None
        or coverage.status != "active"
        or policy is None
        or policy.status != "found"
        or policy.pa_required is not True
    ):
        return {
            "gaps": [],
            "status": "needs_manual_review",
            "errors": [
                "Reliable prescription, coverage, or PA policy information "
                "is unavailable for documentation analysis."
            ],
        }

    try:
        # Retrieve relevant policy passages for documentation requirements.
        documents = retrieve_policy_chunks(
            drug=rx.drug,
            ndc=rx.ndc,
            plan_id=coverage.plan_id,
            focus="documentation",
        )

        if not documents:
            return {
                "gaps": [],
                "status": "needs_manual_review",
                "errors": [
                    "Policy evidence is unavailable for documentation analysis."
                ],
            }

        policy_context = "\n\n---\n\n".join(
            (
                f"Document: {doc.metadata.get('document', doc.metadata.get('source', 'Unknown'))}\n"
                f"Page: {doc.metadata.get('page', 'Unknown')}\n"
                f"Section: {doc.metadata.get('section', 'Unknown')}\n"
                f"Text:\n{doc.page_content}"
            )
            for doc in documents
        )

        # Read submitted-document names from the incoming eRx payload.
        # An absent list means availability is unknown, not necessarily missing.
        erx = state.get("erx") or {}
        submitted_documents = erx.get("submitted_documents")

        if submitted_documents is None:
            submitted_documents = (
                "Not provided; document availability is unknown."
            )
        else:
            submitted_documents = ", ".join(submitted_documents) or "None listed"

        llm = get_llm(FAST_MODEL)
        structured_llm = llm.with_structured_output(GapAnalysis)
        chain = GAPS_PROMPT | structured_llm

        result = chain.invoke(
            {
                "drug": rx.drug or "Not provided",
                "ndc": rx.ndc or "Not provided",
                "plan_id": coverage.plan_id or "Not provided",
                "prescription": rx.model_dump_json(exclude_none=True),
                "submitted_documents": submitted_documents,
                "policy_context": policy_context,
            }
        )

        if not isinstance(result, GapAnalysis):
            result = GapAnalysis.model_validate(result)

        return {"gaps": result.missing_items}

    except Exception:
        # Do not expose raw prescription data or exception details.
        return {
            "gaps": [],
            "status": "needs_manual_review",
            "errors": [
                "Documentation gap analysis failed. Manual review is required."
            ],
        }
