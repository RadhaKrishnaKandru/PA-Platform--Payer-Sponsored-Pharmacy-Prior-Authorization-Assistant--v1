"""Integration tests for PostgreSQL seed data."""

import os

import pytest
from sqlalchemy import func, select

from app.db.models import Base, FormularyEntry
from app.db.postgres import get_session
from app.db.seed import seed


pytestmark = pytest.mark.skipif(
    not os.environ.get("POSTGRES_URL"),
    reason="Set POSTGRES_URL explicitly to run PostgreSQL integration tests.",
)


def test_seed_creates_synthetic_rows_and_missing_policy_entry() -> None:
    seed()

    with get_session() as session:
        counts = {
            table.name: session.scalar(select(func.count()).select_from(table))
            for table in Base.metadata.sorted_tables
        }
        missing_policy = session.scalar(
            select(FormularyEntry).where(
                FormularyEntry.policy_doc.is_(None),
                FormularyEntry.pa_required.is_(True),
            )
        )

    assert counts["members"] == 6
    assert counts["coverage"] == 6
    assert counts["providers"] == 3
    assert missing_policy is not None
