"""Read-only member-coverage lookup."""

from datetime import date

from sqlalchemy import select

from app.db.models import Coverage
from app.db.postgres import get_session
from app.graph.state import CoverageResult, PrescriptionData


class MemberCoveragePrescription(PrescriptionData):
    """Prescription augmented with the member identifier from the eRx."""

    member_id: str | None = None


def check_member_coverage(rx: PrescriptionData) -> CoverageResult:
    """Return the member's current coverage, or unknown when it cannot be found."""
    member_id = getattr(rx, "member_id", None)
    if not member_id:
        return CoverageResult(status="unknown", reason="Member ID is unavailable.")

    with get_session() as session:
        coverage_records = session.scalars(
            select(Coverage)
            .where(Coverage.member_id == member_id)
            .order_by(Coverage.start_date.desc())
        ).all()

    if not coverage_records:
        return CoverageResult(
            status="unknown",
            member_id=member_id,
            reason="No coverage record was found.",
        )

    today = date.today()
    current = next(
        (
            record
            for record in coverage_records
            if record.status.lower() == "active"
            and record.start_date <= today
            and (record.end_date is None or record.end_date >= today)
        ),
        coverage_records[0],
    )
    is_active = (
        current.status.lower() == "active"
        and current.start_date <= today
        and (current.end_date is None or current.end_date >= today)
    )
    return CoverageResult(
        status="active" if is_active else "inactive",
        member_id=member_id,
        plan_id=current.plan_id,
        reason=None if is_active else "Coverage is not active for today's date.",
    )
