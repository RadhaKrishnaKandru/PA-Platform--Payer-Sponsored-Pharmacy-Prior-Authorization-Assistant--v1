"""Create and populate the local database with obviously synthetic records."""

from datetime import date, timedelta

from sqlalchemy import func, select

from app.db.models import (
    Base,
    Claim,
    Coverage,
    Fill,
    FormularyEntry,
    Member,
    Provider,
)
from app.db.postgres import get_engine, get_session


def seed() -> None:
    """Reset the schema and insert the synthetic v1 scenarios."""
    today = date.today()
    engine = get_engine()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    members = [
        Member(
            member_id=f"M00{number}",
            full_name=f"Synthetic Member {number:03d}",
            birth_date=date(1980 + number, 1, 1),
            plan_id="PLAN-A",
        )
        for number in range(1, 7)
    ]
    coverages = [
        Coverage(
            member_id=member.member_id,
            plan_id="PLAN-A",
            status="inactive" if member.member_id == "M002" else "active",
            start_date=today - timedelta(days=365),
            end_date=(
                today - timedelta(days=30)
                if member.member_id == "M002"
                else None
            ),
        )
        for member in members
    ]
    formulary = [
        FormularyEntry(
            plan_id="PLAN-A",
            drug_name="Ozempic",
            ndc="00000-0001-01",
            pa_required=True,
            step_therapy_required=False,
            step_drug_names=[],
            policy_doc="glp1_policy.pdf",
        ),
        FormularyEntry(
            plan_id="PLAN-A",
            drug_name="Metformin",
            ndc="00000-0002-02",
            pa_required=False,
            step_therapy_required=False,
            step_drug_names=[],
        ),
        FormularyEntry(
            plan_id="PLAN-A",
            drug_name="Lisinopril",
            ndc="00000-0003-03",
            pa_required=False,
            step_therapy_required=False,
            step_drug_names=[],
        ),
        FormularyEntry(
            plan_id="PLAN-A",
            drug_name="Oxycodone",
            ndc="00000-0004-04",
            pa_required=True,
            qty_limit=60,
            qty_limit_days=30,
            step_therapy_required=False,
            step_drug_names=[],
            policy_doc="opioid_policy.pdf",
        ),
        FormularyEntry(
            plan_id="PLAN-A",
            drug_name="Trulicity",
            ndc="00000-0005-05",
            pa_required=True,
            step_therapy_required=False,
            step_drug_names=[],
            policy_doc="glp1_policy.pdf",
        ),
        FormularyEntry(
            plan_id="PLAN-A",
            drug_name="Humira",
            ndc="00000-0006-06",
            pa_required=True,
            step_therapy_required=True,
            step_drug_names=["methotrexate"],
            policy_doc="biologic_policy.pdf",
        ),
        FormularyEntry(
            plan_id="PLAN-A",
            drug_name="Synthetic Drug Without Policy",
            ndc="00000-0007-07",
            pa_required=True,
            step_therapy_required=False,
            step_drug_names=[],
            policy_doc=None,
        ),
    ]
    fills = [
        Fill(
            member_id="M004",
            drug_name="Oxycodone",
            ndc="00000-0004-04",
            fill_date=today - timedelta(days=10),
            quantity=30,
            days_supply=30,
            prescriber_npi="9999999991",
        ),
        Fill(
            member_id="M005",
            drug_name="Ozempic",
            ndc="00000-0001-01",
            fill_date=today - timedelta(days=10),
            quantity=1,
            days_supply=30,
            prescriber_npi="9999999992",
        ),
    ]
    claims = [
        Claim(
            member_id="M004",
            drug_name="Oxycodone",
            claim_date=today - timedelta(days=10),
            status="paid",
        ),
        Claim(
            member_id="M005",
            drug_name="Ozempic",
            claim_date=today - timedelta(days=10),
            status="paid",
        ),
    ]
    providers = [
        Provider(
            npi="9999999991",
            name="Synthetic Provider One",
            specialty="Primary Care",
            network_status="in_network",
            fax="555-0101",
        ),
        Provider(
            npi="9999999992",
            name="Synthetic Provider Two",
            specialty="Endocrinology",
            network_status="in_network",
            fax="555-0102",
        ),
        Provider(
            npi="9999999993",
            name="Synthetic Provider Three",
            specialty="Rheumatology",
            network_status="out_of_network",
            fax="555-0103",
        ),
    ]

    with get_session() as session:
        session.add_all(members)
        session.flush()
        session.add_all(coverages + formulary + providers)
        session.flush()
        session.add_all(fills + claims)
        session.commit()
        row_counts = {
            table.name: session.scalar(select(func.count()).select_from(table))
            for table in Base.metadata.sorted_tables
        }

    for table_name, row_count in row_counts.items():
        print(f"{table_name}: {row_count}")


if __name__ == "__main__":
    seed()
