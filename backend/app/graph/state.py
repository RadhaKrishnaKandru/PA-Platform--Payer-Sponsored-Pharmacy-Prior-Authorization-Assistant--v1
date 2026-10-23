
from typing import Literal, NotRequired, TypedDict

from pydantic import BaseModel, Field




class PrescriptionData(BaseModel):
    drug: str | None = None
    ndc: str | None = None
    quantity: float | None = None
    days_supply: int | None = None
    prescriber: str | None = None
    diagnosis: str | None = None


class CoverageResult(BaseModel):
    status: Literal["active", "inactive", "unknown"]
    member_id: str | None = None
    plan_id: str | None = None
    reason: str | None = None


class PolicyCitation(BaseModel):
    document: str
    page: int = Field(ge=1)
    section: str


class PolicyResult(BaseModel):
    status: Literal["found", "not_found", "low_confidence", "conflict"]
    pa_required: bool | None = None
    reasons: list[str] = Field(default_factory=list)
    citations: list[PolicyCitation] = Field(default_factory=list)


class MissingItem(BaseModel):
    item: str
    reason: str


class RiskSignal(BaseModel):
    type: Literal[
        "early_refill",
        "duplicate_therapy",
        "quantity_limit",
        "claims_history",
        "other",
    ]
    severity: Literal["low", "medium", "high"]
    detail: str


class ProviderMessage(BaseModel):
    message_type: Literal["fax", "email", "portal"]
    content: str
    status: Literal["draft"] = "draft"


class CaseSummary(BaseModel):
    coverage_status: Literal["active", "inactive", "unknown"]
    pa_required: bool | None = None
    status: Literal["ok", "stopped", "needs_manual_review"]
    explanation: str


class TraceEvent(BaseModel):
    node: str
    timestamp: str
    outcome: Literal["success", "failure", "skipped"]
    duration_ms: int | None = None
    error_category: str | None = None




class CaseState(TypedDict):

    erx: dict

   
    rx: NotRequired[PrescriptionData]
    coverage: NotRequired[CoverageResult]
    policy: NotRequired[PolicyResult]
    gaps: NotRequired[list[MissingItem]]
    utilization: NotRequired[list[RiskSignal]]
    provider_msg: NotRequired[ProviderMessage]
    summary: NotRequired[CaseSummary]

    
    status: NotRequired[
        Literal["ok", "stopped", "needs_manual_review"]
    ]
    errors: NotRequired[list[str]]
    trace: NotRequired[list[TraceEvent]]
