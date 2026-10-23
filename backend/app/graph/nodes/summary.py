
"""Final LangGraph node for assembling the PA case summary."""

from app.graph.state import CaseState, CaseSummary


def _get(obj, key: str, default=None):
    """Read a field from either a Pydantic model or a dictionary."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def summary_node(state: CaseState) -> dict:
    """Build a final summary from the accumulated workflow state."""

    rx = state.get("rx")
    coverage = state.get("coverage")
    policy = state.get("policy")
    gaps = state.get("gaps", [])
    utilization = state.get("utilization", [])
    provider_msg = state.get("provider_msg")

    # Preserve any manual-review status established by earlier nodes.
    current_status = state.get("status", "ok")

    coverage_status = _get(coverage, "status", "unknown")
    policy_status = _get(policy, "status")
    pa_required = _get(policy, "pa_required")

    explanation_parts = []

    # 1. Prescription information
    if rx is not None:
        drug = _get(rx, "drug")
        if drug:
            explanation_parts.append(f"Prescription: {drug}.")
    else:
        explanation_parts.append(
            "Prescription details could not be validated."
        )

    # 2. Coverage findings
    if coverage_status == "active":
        explanation_parts.append("Member coverage is active.")
    elif coverage_status == "inactive":
        explanation_parts.append(
            "Member coverage is inactive. Further processing was stopped."
        )
        current_status = "stopped"
    else:
        explanation_parts.append(
            "Coverage could not be verified."
        )
        current_status = "needs_manual_review"

    # 3. Policy findings
    if policy_status == "found" and pa_required is True:
        explanation_parts.append(
            "The retrieved payer policy indicates that PA is required."
        )
    elif policy_status == "found" and pa_required is False:
        explanation_parts.append(
            "The retrieved payer policy indicates that PA is not required."
        )
    elif policy_status == "conflict":
        explanation_parts.append(
            "Retrieved policy evidence conflicts and requires manual review."
        )
        current_status = "needs_manual_review"
    elif policy_status == "low_confidence":
        explanation_parts.append(
            "Policy evidence is insufficient for a reliable conclusion."
        )
        current_status = "needs_manual_review"
    elif policy_status == "not_found":
        explanation_parts.append(
            "No relevant payer policy was found."
        )
        current_status = "needs_manual_review"
    else:
        explanation_parts.append(
            "The PA requirement could not be established."
        )
        current_status = "needs_manual_review"

    # 4. Documentation gaps
    if gaps:
        gap_names = [
            _get(gap, "item", "Unspecified documentation")
            for gap in gaps
        ]
        explanation_parts.append(
            "Potential documentation gaps: "
            + "; ".join(gap_names)
            + "."
        )
    elif policy_status == "found" and pa_required is True:
        explanation_parts.append(
            "No documentation gaps were identified by the current analysis. "
            "This does not guarantee that the submission is complete."
        )

    # 5. Utilization findings
    if utilization:
        risk_descriptions = [
            _get(risk, "detail", "Utilization signal identified")
            for risk in utilization
        ]
        explanation_parts.append(
            "Utilization signals for review: "
            + "; ".join(risk_descriptions)
            + "."
        )
    else:
        explanation_parts.append(
            "No utilization signals were identified by the current checks."
        )

    # 6. Guardrail and provider-message status
    guardrail_passed = state.get("guardrail_passed")

    if provider_msg is not None:
        if guardrail_passed is True:
            explanation_parts.append(
                "A provider communication draft passed guardrail checks; "
                "it has not been sent."
            )
        else:
            explanation_parts.append(
                "A provider communication draft requires manual review."
            )
            current_status = "needs_manual_review"

    # Do not overwrite a manual-review status set by a previous node.
    if current_status not in {"ok", "stopped", "needs_manual_review"}:
        current_status = "needs_manual_review"

    summary = CaseSummary(
        coverage_status=coverage_status,
        pa_required=(
            pa_required
            if policy_status == "found"
            else None
        ),
        status=current_status,
        explanation=" ".join(explanation_parts),
    )

    return {
        "summary": summary,
        "status": current_status,
    }
