
"""LangGraph node for deterministic prescription utilization checks."""

from datetime import date, datetime
from typing import Any

from app.graph.state import CaseState, RiskSignal
from app.tools.fills import get_member_fills


def _parse_date(value: Any) -> date | None:
    """Convert a supported date value to a date."""
    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None

    return None


def _normalize_drug(value: str | None) -> str:
    """Normalize a drug name for exact-name comparisons."""
    return " ".join((value or "").lower().split())


def utilization_node(state: CaseState) -> dict:
    """Flag utilization concerns using member claims/fill history."""

    rx = state.get("rx")
    coverage = state.get("coverage")

    if rx is None or coverage is None:
        return {
            "utilization": [],
            "status": "needs_manual_review",
            "errors": [
                "Prescription or coverage information is unavailable "
                "for utilization checks."
            ],
        }

    if coverage.status != "active" or not coverage.member_id:
        return {
            "utilization": [],
            "status": "needs_manual_review",
            "errors": [
                "Active coverage and a verified member ID are required "
                "for utilization checks."
            ],
        }

    risks: list[RiskSignal] = []

    try:
        # Expected helper: return fill/claim records for this member.
        fills = get_member_fills(coverage.member_id)

        today = date.today()
        target_drug = _normalize_drug(rx.drug)

        for fill in fills:
            fill_drug = _normalize_drug(fill.get("drug"))
            fill_date = _parse_date(fill.get("fill_date"))

            # Compare the exact normalized drug name only.
            if target_drug and fill_drug == target_drug:
                # A same-drug historical fill is a signal to inspect,
                # not proof of duplicate therapy.
                risks.append(
                    RiskSignal(
                        type="duplicate_therapy",
                        severity="low",
                        detail=(
                            "A previous fill for the same drug was found. "
                            "Verify whether it represents a duplicate claim "
                            "or a legitimate continuation."
                        ),
                    )
                )

                previous_days_supply = fill.get("days_supply")

                if (
                    fill_date is not None
                    and isinstance(previous_days_supply, int)
                    and not isinstance(previous_days_supply, bool)
                    and previous_days_supply > 0
                    and fill_date <= today
                ):
                    expected_runout = date.fromordinal(
                        fill_date.toordinal() + previous_days_supply
                    )

                    if today < expected_runout:
                        days_remaining = (
                            expected_runout - today
                        ).days

                        risks.append(
                            RiskSignal(
                                type="early_refill",
                                severity="medium",
                                detail=(
                                    "A previous fill for the same drug may "
                                    f"have approximately {days_remaining} "
                                    "days of supply remaining. Verify the "
                                    "claim history and applicable plan rules."
                                ),
                            )
                        )

        # This node does not infer quantity limits from the drug name.
        # Add a deterministic plan-specific quantity-limit check once
        # authoritative limit rules are available in the tool layer.

        return {"utilization": risks}

    except Exception:
        # Avoid exposing prescription data or raw exception details.
        return {
            "utilization": [],
            "status": "needs_manual_review",
            "errors": [
                "Utilization verification failed. Manual review is required."
            ],
        }
