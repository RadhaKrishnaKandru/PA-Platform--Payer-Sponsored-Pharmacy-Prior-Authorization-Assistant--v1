"""Synthetic fill-history lookup used until PostgreSQL is wired."""

from datetime import date, timedelta


def get_member_fills(member_id: str) -> list[dict[str, str | int]]:
    """Return a synthetic prior fill for local development."""
    del member_id
    return [
        {
            "drug": "Example Medication",
            "fill_date": (date.today() - timedelta(days=45)).isoformat(),
            "days_supply": 30,
        }
    ]
