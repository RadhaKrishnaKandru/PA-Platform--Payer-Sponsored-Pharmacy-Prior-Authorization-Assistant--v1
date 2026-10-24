"""Read-only prescription fill and history lookups."""

from datetime import date

from pydantic import BaseModel
from sqlalchemy import func, select

from app.db.models import Claim, Fill, PAHistory
from app.db.postgres import get_session


class ClaimRecord(BaseModel):
    """Minimal typed claim record for deterministic utilization checks."""

    drug_name: str
    claim_date: date
    status: str
    reject_code: str | None = None


class PAHistoryRecord(BaseModel):
    """Minimal typed prior-authorization history record."""

    drug_name: str
    request_date: date
    outcome: str


def get_member_fills(member_id: str) -> list[dict[str, str | int]]:
    """Return a member's fill history in the established graph-tool shape."""
    with get_session() as session:
        fills = session.scalars(
            select(Fill)
            .where(Fill.member_id == member_id)
            .order_by(Fill.fill_date.desc())
        ).all()

    return [
        {
            "drug": fill.drug_name,
            "ndc": fill.ndc,
            "fill_date": fill.fill_date.isoformat(),
            "quantity": fill.quantity,
            "days_supply": fill.days_supply,
            "prescriber_npi": fill.prescriber_npi,
        }
        for fill in fills
    ]


def get_member_claims(
    member_id: str, drug_name: str | None = None
) -> list[ClaimRecord]:
    """Return the member's claims, optionally filtered by exact drug name."""
    statement = select(Claim).where(Claim.member_id == member_id)
    if drug_name is not None:
        statement = statement.where(
            func.lower(Claim.drug_name) == drug_name.strip().lower()
        )

    with get_session() as session:
        claims = session.scalars(statement.order_by(Claim.claim_date.desc())).all()

    return [
        ClaimRecord(
            drug_name=claim.drug_name,
            claim_date=claim.claim_date,
            status=claim.status,
            reject_code=claim.reject_code,
        )
        for claim in claims
    ]


def get_pa_history(
    member_id: str, drug_name: str | None = None
) -> list[PAHistoryRecord]:
    """Return the member's PA history, optionally filtered by exact drug name."""
    statement = select(PAHistory).where(PAHistory.member_id == member_id)
    if drug_name is not None:
        statement = statement.where(
            func.lower(PAHistory.drug_name) == drug_name.strip().lower()
        )

    with get_session() as session:
        records = session.scalars(
            statement.order_by(PAHistory.request_date.desc())
        ).all()

    return [
        PAHistoryRecord(
            drug_name=record.drug_name,
            request_date=record.request_date,
            outcome=record.outcome,
        )
        for record in records
    ]
