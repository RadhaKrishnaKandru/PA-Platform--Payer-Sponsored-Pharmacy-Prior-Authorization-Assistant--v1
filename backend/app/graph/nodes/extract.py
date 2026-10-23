
"""LangGraph node for extracting prescription data from an eRx."""

from app.graph.state import CaseState, PrescriptionData


def extract_node(state: CaseState) -> dict:
    """Validate and normalize prescription data from the incoming eRx."""

    erx = state.get("erx")

    if not isinstance(erx, dict) or not erx:
        return {
            "status": "needs_manual_review",
            "errors": [
                "eRx data is missing or invalid. Manual review is required."
            ],
        }

    try:
        # Validate the incoming eRx against the Pydantic model.
        rx = PrescriptionData.model_validate(erx)

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
