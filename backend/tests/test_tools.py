"""Integration tests for deterministic PostgreSQL tools and utilization rules."""

import os

import pytest

from app.db.seed import seed
from app.graph.nodes.utilization import utilization_node
from app.graph.state import CoverageResult, PrescriptionData, RiskSignal
from app.tools.coverage import MemberCoveragePrescription, check_member_coverage
from app.tools.formulary import get_formulary_entry


pytestmark = pytest.mark.skipif(
    not os.environ.get("POSTGRES_URL"),
    reason="Set POSTGRES_URL explicitly to run PostgreSQL integration tests.",
)


@pytest.fixture(scope="module", autouse=True)
def seeded_database() -> None:
    seed()


def _utilization(
    member_id: str, drug: str, quantity: float
) -> list[RiskSignal]:
    result = utilization_node(
        {
            "rx": PrescriptionData(
                drug=drug,
                quantity=quantity,
            ),
            "coverage": CoverageResult(
                status="active",
                member_id=member_id,
                plan_id="PLAN-A",
            ),
        }
    )
    return result["utilization"]


def test_m002_coverage_is_inactive() -> None:
    coverage = check_member_coverage(
        MemberCoveragePrescription(drug="Metformin", member_id="M002")
    )

    assert coverage.status == "inactive"


def test_m004_flags_early_refill_and_quantity_limit() -> None:
    risks = _utilization("M004", "Oxycodone", 40)
    risk_types = {risk.type for risk in risks}

    assert "early_refill" in risk_types
    assert "quantity_limit" in risk_types


def test_m005_flags_duplicate_therapy() -> None:
    risks = _utilization("M005", "Trulicity", 1)

    assert any(risk.type == "duplicate_therapy" for risk in risks)


def test_m006_flags_missing_step_therapy_claim() -> None:
    risks = _utilization("M006", "Humira", 1)

    assert any(
        risk.type == "claims_history" and "methotrexate" in risk.detail.lower()
        for risk in risks
    )


def test_formulary_entry_can_have_no_policy_document() -> None:
    entry = get_formulary_entry(
        "PLAN-A",
        drug_name="Synthetic Drug Without Policy",
    )

    assert entry is not None
    assert entry.pa_required is True
    assert entry.policy_doc is None
