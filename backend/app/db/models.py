"""SQLAlchemy models for synthetic payer and utilization data."""

from datetime import date

from sqlalchemy import ARRAY, Boolean, Date, ForeignKey, Index, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Shared declarative base for the relational models."""


class Member(Base):
    """Covered member demographics and plan association."""

    __tablename__ = "members"

    member_id: Mapped[str] = mapped_column(String, primary_key=True)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    plan_id: Mapped[str] = mapped_column(String, nullable=False)


class Coverage(Base):
    """Member coverage period and status."""

    __tablename__ = "coverage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[str] = mapped_column(
        ForeignKey("members.member_id"), nullable=False, index=True
    )
    plan_id: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class FormularyEntry(Base):
    """Plan-specific drug authorization and utilization criteria."""

    __tablename__ = "formulary"
    __table_args__ = (Index("ix_formulary_plan_drug", "plan_id", "drug_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[str] = mapped_column(String, nullable=False)
    drug_name: Mapped[str] = mapped_column(String, nullable=False)
    ndc: Mapped[str] = mapped_column(String, nullable=False)
    pa_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    qty_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    qty_limit_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    step_therapy_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    step_drug_names: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list
    )
    policy_doc: Mapped[str | None] = mapped_column(String, nullable=True)


class Fill(Base):
    """Dispensed prescription fill."""

    __tablename__ = "fills"
    __table_args__ = (Index("ix_fills_member_drug", "member_id", "drug_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[str] = mapped_column(
        ForeignKey("members.member_id"), nullable=False
    )
    drug_name: Mapped[str] = mapped_column(String, nullable=False)
    ndc: Mapped[str] = mapped_column(String, nullable=False)
    fill_date: Mapped[date] = mapped_column(Date, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    days_supply: Mapped[int] = mapped_column(Integer, nullable=False)
    prescriber_npi: Mapped[str] = mapped_column(String, nullable=False)


class Claim(Base):
    """Historical adjudicated claim."""

    __tablename__ = "claims_history"
    __table_args__ = (Index("ix_claims_member_drug", "member_id", "drug_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[str] = mapped_column(
        ForeignKey("members.member_id"), nullable=False
    )
    drug_name: Mapped[str] = mapped_column(String, nullable=False)
    claim_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    reject_code: Mapped[str | None] = mapped_column(String, nullable=True)


class PAHistory(Base):
    """Prior authorization request outcome."""

    __tablename__ = "pa_history"
    __table_args__ = (Index("ix_pa_history_member_drug", "member_id", "drug_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[str] = mapped_column(
        ForeignKey("members.member_id"), nullable=False
    )
    drug_name: Mapped[str] = mapped_column(String, nullable=False)
    request_date: Mapped[date] = mapped_column(Date, nullable=False)
    outcome: Mapped[str] = mapped_column(String, nullable=False)


class Provider(Base):
    """Prescriber directory information."""

    __tablename__ = "providers"

    npi: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    specialty: Mapped[str] = mapped_column(String, nullable=False)
    network_status: Mapped[str] = mapped_column(String, nullable=False)
    fax: Mapped[str] = mapped_column(String, nullable=False)
