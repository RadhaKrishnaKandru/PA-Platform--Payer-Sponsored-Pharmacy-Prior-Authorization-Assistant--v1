"""Read-only prescriber directory lookup."""

from pydantic import BaseModel
from sqlalchemy import select

from app.db.models import Provider
from app.db.postgres import get_session


class ProviderRecord(BaseModel):
    """Typed provider contact information."""

    specialty: str
    network_status: str
    fax: str


def get_provider(npi: str) -> ProviderRecord | None:
    """Return a provider's specialty and contact details."""
    with get_session() as session:
        provider = session.scalar(select(Provider).where(Provider.npi == npi))

    if provider is None:
        return None
    return ProviderRecord(
        specialty=provider.specialty,
        network_status=provider.network_status,
        fax=provider.fax,
    )
