
"""LangGraph node for member coverage verification."""

from app.graph.state import CaseState, CoverageResult
from app.graph.nodes._trace import traced
from app.tools.coverage import (
    MemberCoveragePrescription,
    check_member_coverage,
)




# class CoverageResult(BaseModel):
    # status: Literal["active", "inactive", "unknown"]
    # member_id: str | None = None
    # plan_id: str | None = None
    # reason: str | None = None
# 


@traced("coverage")
def coverage_node(state: CaseState) -> dict:
    """Verify coverage and route cases with unknown or inactive coverage."""

    rx = state.get("rx")

    if rx is None:
        return {
            "status": "needs_manual_review",
            "errors": [
                "Prescription extraction is unavailable; coverage cannot be checked."
            ],
        }

    try:
        # Deterministic lookup against PostgreSQL through the tools layer.
        erx = state.get("erx")
        member_id = erx.get("member_id") if isinstance(erx, dict) else None
        lookup_rx = MemberCoveragePrescription.model_validate(
            {**rx.model_dump(), "member_id": member_id}
        )
        result = check_member_coverage(lookup_rx)

        if not isinstance(result, CoverageResult):
            result = CoverageResult.model_validate(result)

        if result.status == "inactive":
            return {
                "coverage": result,
                "status": "stopped",
            }

        if result.status == "unknown":
            return {
                "coverage": result,
                "status": "needs_manual_review",
            }

        return {"coverage": result}

    except Exception:
        # Avoid exposing database errors or sensitive data in graph state.
        return {
            "status": "needs_manual_review",
            "errors": [
                "Coverage verification failed. Manual review is required."
            ],
        }
