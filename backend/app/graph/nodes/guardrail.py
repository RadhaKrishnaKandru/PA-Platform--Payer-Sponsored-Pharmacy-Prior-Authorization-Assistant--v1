
"""Deterministic guardrails for PA case outputs and provider drafts."""

import re

from app.graph.state import CaseState, ProviderMessage
from app.graph.nodes._trace import traced


# Block unsupported final determinations.
FORBIDDEN_CLAIMS = [
    re.compile(r"\b(?:approved|denied)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:will|guaranteed to|certain to)\s+"
        r"(?:be approved|be denied|get approval)\b",
        re.IGNORECASE,
    ),
]

# Block language that recommends changing or substituting medication.
MEDICATION_RECOMMENDATIONS = [
    re.compile(
        r"\b(?:switch to|replace with|use instead of|"
        r"take instead of|I recommend|we recommend)\b",
        re.IGNORECASE,
    ),
]

# Examples of high-risk sensitive data that should not appear in a draft.
SENSITIVE_PATTERNS = [
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # US SSN pattern
    re.compile(
        r"\b(?:api[_ -]?key|access[_ -]?token|secret[_ -]?key)"
        r"\s*[:=]\s*\S+",
        re.IGNORECASE,
    ),
]


def _get(obj, key: str, default=None):
    """Read a field from either a Pydantic model or a dictionary."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _validate_case(state: CaseState) -> list[str]:
    """Return validation failures without exposing sensitive input."""

    failures: list[str] = []

    policy = state.get("policy")
    provider_msg = state.get("provider_msg")
    status = state.get("status")

    # Do not allow an uncertain policy to support a definitive PA conclusion.
    if policy is not None:
        policy_status = _get(policy, "status")
        pa_required = _get(policy, "pa_required")
        citations = _get(policy, "citations", [])

        if policy_status == "found":
            if pa_required is None:
                failures.append(
                    "Policy is marked found but has no PA conclusion."
                )

            if not citations:
                failures.append(
                    "Policy conclusion has no supporting citations."
                )

        elif pa_required is not None:
            failures.append(
                "Uncertain policy status contains a definitive PA conclusion."
            )

    if status == "stopped":
        # Inactive coverage must not produce an actionable PA draft.
        if provider_msg is not None:
            failures.append(
                "A provider message exists for a stopped case."
            )

    if provider_msg is not None:
        content = _get(provider_msg, "content", "")

        if not isinstance(content, str) or not content.strip():
            failures.append("Provider message is empty.")
            content = ""

        for pattern in FORBIDDEN_CLAIMS:
            if pattern.search(content):
                failures.append(
                    "Provider message contains an approval or denial claim."
                )
                break

        for pattern in MEDICATION_RECOMMENDATIONS:
            if pattern.search(content):
                failures.append(
                    "Provider message contains medication recommendation language."
                )
                break

        for pattern in SENSITIVE_PATTERNS:
            if pattern.search(content):
                failures.append(
                    "Provider message contains a blocked sensitive-data pattern."
                )
                break

        if _get(provider_msg, "status") != "draft":
            failures.append(
                "Provider message must remain in draft status."
            )

    return failures


@traced("guardrail")
def guardrail_node(state: CaseState) -> dict:
    """Validate workflow outputs and control one retry before safe fallback."""

    attempts = state.get("guardrail_attempts", 0)
    failures = _validate_case(state)

    if not failures:
        return {
            "guardrail_passed": True,
            "guardrail_attempts": attempts,
            "guardrail_violations": [],
        }

    next_attempt = attempts + 1

    # One retry is permitted. After the retry fails, replace the draft
    # with a neutral fallback and require human review.
    if next_attempt >= 2:
        safe_message = ProviderMessage(
            message_type="fax",
            content=(
                "This case requires manual review before any provider "
                "communication is sent. Please review the available "
                "prescription information and applicable payer policy."
            ),
            status="draft",
        )

        return {
            "provider_msg": safe_message,
            "guardrail_passed": False,
            "guardrail_attempts": next_attempt,
            "guardrail_violations": failures,
            "status": "needs_manual_review",
            "errors": [
                "Guardrail validation failed after one retry. "
                "The draft was replaced with a safe fallback."
            ],
        }

    # The graph should route back to provider_msg for one regeneration.
    return {
        "guardrail_passed": False,
        "guardrail_attempts": next_attempt,
        "guardrail_violations": failures,
    }
