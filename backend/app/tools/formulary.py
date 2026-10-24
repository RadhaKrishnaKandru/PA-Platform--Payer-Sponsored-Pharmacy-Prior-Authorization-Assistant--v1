"""Read-only plan formulary lookup."""

from pydantic import BaseModel
from sqlalchemy import func, or_, select

from app.db.models import FormularyEntry
from app.db.postgres import get_session


class FormularyRecord(BaseModel):
    """Typed formulary criteria consumed by graph nodes."""

    plan_id: str
    drug_name: str
    ndc: str
    pa_required: bool
    qty_limit: int | None = None
    qty_limit_days: int | None = None
    min_age: int | None = None
    step_therapy_required: bool
    step_drug_names: list[str]
    policy_doc: str | None = None


def get_formulary_entry(
    plan_id: str, drug_name: str | None = None, ndc: str | None = None
) -> FormularyRecord | None:
    """Find the plan entry by normalized drug name and/or exact NDC."""
    conditions = []
    if drug_name and drug_name.strip():
        conditions.append(
            func.lower(FormularyEntry.drug_name) == drug_name.strip().lower()
        )
    if ndc and ndc.strip():
        conditions.append(FormularyEntry.ndc == ndc.strip())
    if not conditions:
        return None

    statement = (
        select(FormularyEntry)
        .where(FormularyEntry.plan_id == plan_id, or_(*conditions))
        .order_by(FormularyEntry.id)
        .limit(1)
    )
    with get_session() as session:
        entry = session.scalar(statement)

    if entry is None:
        return None
    return FormularyRecord(
        plan_id=entry.plan_id,
        drug_name=entry.drug_name,
        ndc=entry.ndc,
        pa_required=entry.pa_required,
        qty_limit=entry.qty_limit,
        qty_limit_days=entry.qty_limit_days,
        min_age=entry.min_age,
        step_therapy_required=entry.step_therapy_required,
        step_drug_names=entry.step_drug_names,
        policy_doc=entry.policy_doc,
    )
