
"""LangGraph node for deterministic prescription utilization checks."""

from datetime import date, datetime, timedelta
from typing import Any

from app.constants import DRUG_CLASSES
from app.graph.nodes._trace import traced
from app.graph.state import CaseState, RiskSignal
from app.tools.fills import get_member_claims, get_member_fills
from app.tools.formulary import get_formulary_entry


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


def _fill_value(fill: dict[str, str | int], key: str) -> Any:
    """Read a fill field while preserving the established dictionary interface."""
    return fill.get(key)


@traced("utilization")
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
        fills = get_member_fills(coverage.member_id)
        claims = get_member_claims(coverage.member_id)
        formulary = get_formulary_entry(
            coverage.plan_id or "",
            drug_name=rx.drug,
            ndc=rx.ndc,
        )

        today = date.today()
        target_drug = _normalize_drug(rx.drug)
        target_class = DRUG_CLASSES.get(target_drug)
        requested_quantity = rx.quantity
        recent_quantity = 0
        quantity_window = (
            formulary.qty_limit_days
            if formulary is not None and formulary.qty_limit_days
            else None
        )
        quantity_cutoff = (
            today - timedelta(days=quantity_window)
            if quantity_window is not None
            else None
        )

        for fill in fills:
            fill_drug = _normalize_drug(_fill_value(fill, "drug"))
            fill_date = _parse_date(_fill_value(fill, "fill_date"))
            days_supply = _fill_value(fill, "days_supply")
            quantity = _fill_value(fill, "quantity")

            if (
                quantity_cutoff is not None
                and target_drug
                and fill_drug == target_drug
                and fill_date is not None
                and fill_date >= quantity_cutoff
                and fill_date <= today
                and isinstance(quantity, int)
                and not isinstance(quantity, bool)
            ):
                recent_quantity += quantity

            if (
                target_drug
                and target_class is not None
                and fill_drug != target_drug
                and DRUG_CLASSES.get(fill_drug) == target_class
                and fill_date is not None
                and isinstance(days_supply, int)
                and not isinstance(days_supply, bool)
                and days_supply > 0
                and fill_date <= today
                and fill_date + timedelta(days=days_supply) > today
            ):
                risks.append(
                    RiskSignal(
                        type="duplicate_therapy",
                        severity="medium",
                        detail=(
                            "An active fill for another drug in the same "
                            "therapeutic class was found. Verify concurrent "
                            "therapy with the prescriber."
                        ),
                    )
                )

            if (
                target_drug
                and fill_drug == target_drug
                and fill_date is not None
                and isinstance(days_supply, int)
                and not isinstance(days_supply, bool)
                and days_supply > 0
                and fill_date <= today
                and fill_date
                + timedelta(days=0.75 * days_supply)
                > today
            ):
                risks.append(
                    RiskSignal(
                        type="early_refill",
                        severity="medium",
                        detail=(
                            "A prior fill is within the plan's early-refill "
                            "review window. Verify the claim history and "
                            "applicable plan rules."
                        ),
                    )
                )

        if (
            formulary is not None
            and formulary.qty_limit is not None
            and requested_quantity is not None
            and requested_quantity + recent_quantity > formulary.qty_limit
        ):
            risks.append(
                RiskSignal(
                    type="quantity_limit",
                    severity="medium",
                    detail=(
                        "The requested quantity plus recent fills exceeds "
                        "the plan's quantity limit. Verify applicable "
                        "dispensing rules."
                    ),
                )
            )

        if formulary is not None and formulary.step_therapy_required:
            claimed_drugs = {
                _normalize_drug(claim.drug_name) for claim in claims
            }
            missing_steps = [
                step_drug
                for step_drug in formulary.step_drug_names
                if _normalize_drug(step_drug) not in claimed_drugs
            ]
            if missing_steps:
                risks.append(
                    RiskSignal(
                        type="claims_history",
                        severity="medium",
                        detail=(
                            "Claims history does not show the plan's "
                            "step-therapy medication(s): "
                            f"{', '.join(missing_steps)}. Verify prior "
                            "therapy documentation with the provider."
                        ),
                    )
                )

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
