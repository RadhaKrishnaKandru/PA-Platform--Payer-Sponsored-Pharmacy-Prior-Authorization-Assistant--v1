"""Integration tests for PostgreSQL seed data."""

import pytest
from sqlalchemy import func, select

from app.config import get_settings
from app.db.models import Base, FormularyEntry
from app.db.postgres import get_session
from app.db.seed import seed

postgres_url = get_settings().postgres_url
pytestmark = pytest.mark.skipif(
    postgres_url is None or not postgres_url.get_secret_value().strip(),
    reason="Set POSTGRES_URL in backend/.env or the shell to run PostgreSQL integration tests.",
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
