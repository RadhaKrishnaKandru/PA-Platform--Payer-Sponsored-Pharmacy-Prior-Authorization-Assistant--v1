"""Synthetic member-coverage lookup used until PostgreSQL is wired."""

from app.graph.state import CoverageResult, PrescriptionData


def check_member_coverage(rx: PrescriptionData) -> CoverageResult:
    """Return a synthetic active coverage record for local development."""
    del rx
    return CoverageResult(
        status="active",
        member_id="SYNTH-MEMBER-001",
        plan_id="SYNTH-PLAN-001",
    )
