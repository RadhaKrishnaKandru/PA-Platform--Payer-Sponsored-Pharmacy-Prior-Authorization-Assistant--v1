
"""LangGraph node for extracting prescription data from an eRx."""

import json

from langchain_core.prompts import ChatPromptTemplate

from app.graph.state import CaseState, PrescriptionData
from app.graph.nodes._trace import traced
from app.llm.client import FAST_MODEL, get_llm

EXTRACTION_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
Extract only the supported prescription fields from the supplied eRx:
drug, ndc, quantity, days_supply, prescriber, and diagnosis.
Do not infer missing values. Return the requested structured output.
            """,
        ),
        ("human", "eRx information:\n{erx}"),
    ]
)


@traced("extract")
def extract_node(state: CaseState) -> dict:
    """Validate and normalize prescription data from the incoming eRx."""

    erx = state.get("erx")

    if not isinstance(erx, (dict, str)) or not erx:
        return {
            "status": "needs_manual_review",
            "errors": [
                "eRx data is missing or invalid. Manual review is required."
            ],
        }

    try:
        expected_fields = (
            "drug",
            "ndc",
            "quantity",
            "days_supply",
            "prescriber",
            "diagnosis",
        )
        has_all_fields = (
            isinstance(erx, dict)
            and all(
                field in erx and erx[field] not in (None, "")
                for field in expected_fields
            )
        )

        if has_all_fields:
            rx = PrescriptionData.model_validate(erx)
        else:
            structured_llm = get_llm(FAST_MODEL).with_structured_output(
                PrescriptionData
            )
            chain = EXTRACTION_PROMPT | structured_llm
            result = chain.invoke(
                {
                    "erx": (
                        json.dumps(erx, default=str)
                        if isinstance(erx, dict)
                        else erx
                    )
                }
            )
            rx = (
                result
                if isinstance(result, PrescriptionData)
                else PrescriptionData.model_validate(result)
            )

        # Ensure the required drug identifier is present.
        if not rx.drug and not rx.ndc:
            return {
                "rx": rx,
                "status": "needs_manual_review",
                "errors": [
                    "Prescription drug name or NDC is missing."
                ],
            }

        return {
            "rx": rx,
            "status": "ok",
        }

    except Exception:
        # Avoid exposing raw input or exception details in the response.
        return {
            "status": "needs_manual_review",
            "errors": [
                "Prescription data validation failed. Manual review is required."
            ],
        }
