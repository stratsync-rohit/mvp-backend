"""
Pydantic v2 schemas for the Risk resource.

Money values use `int` (whole USD units) per project decision - this keeps
MongoDB serialization simple while still being safe for the amounts
involved in this domain.
"""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict

from app.models.risk import Severity, RiskStatus, StepStatus
from app.schemas.common import Vessel, ActionButton


# ---------------------------------------------------------------------------
# Nested building blocks
# ---------------------------------------------------------------------------

class RiskDetails(BaseModel):
    underlyingExposure: list[str] = Field(default_factory=list)
    impact: list[str] = Field(default_factory=list)


class MitigationStep(BaseModel):
    step: int
    title: str
    description: str
    owner: str
    status: StepStatus = StepStatus.PENDING


class MitigationPlan(BaseModel):
    summary: Optional[str] = None
    steps: list[MitigationStep] = Field(default_factory=list)
    lastUpdated: Optional[datetime] = None


class Tracking(BaseModel):
    enabled: bool = False
    trackedBy: Optional[str] = None
    trackedAt: Optional[datetime] = None


class Assignment(BaseModel):
    assignedTo: Optional[str] = None
    assignedBy: Optional[str] = None
    assignedAt: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Create / Update
# ---------------------------------------------------------------------------

class RiskCreate(BaseModel):
    riskId: str = Field(..., description="Unique business identifier, e.g. RSK-OP-0821")
    title: str
    vessel: Vessel
    accountId: str
    severity: Severity
    summary: str
    fundingShortfall: int = 0
    paymentsAtRisk: int = 0
    deadline: date
    accountRisk: str = "Medium"
    status: RiskStatus = RiskStatus.OPEN
    details: RiskDetails = Field(default_factory=RiskDetails)
    mitigationPlan: MitigationPlan
    tracking: Tracking = Field(default_factory=Tracking)
    assignment: Assignment = Field(default_factory=Assignment)


class RiskUpdate(BaseModel):
    """All fields optional to support PATCH-style partial updates.

    riskId is intentionally NOT included here - it must never change.
    """
    title: Optional[str] = None
    vessel: Optional[Vessel] = None
    accountId: Optional[str] = None
    severity: Optional[Severity] = None
    summary: Optional[str] = None
    fundingShortfall: Optional[int] = None
    paymentsAtRisk: Optional[int] = None
    deadline: Optional[date] = None
    accountRisk: Optional[str] = None
    status: Optional[RiskStatus] = None
    details: Optional[RiskDetails] = None
    mitigationPlan: Optional[MitigationPlan] = None
    tracking: Optional[Tracking] = None
    assignment: Optional[Assignment] = None


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------

class RiskResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    riskId: str
    title: str
    vessel: Vessel
    accountId: str
    severity: Severity
    summary: str
    fundingShortfall: int
    paymentsAtRisk: int
    deadline: date
    accountRisk: str
    status: RiskStatus
    details: RiskDetails
    mitigationPlan: MitigationPlan
    tracking: Tracking
    assignment: Assignment
    createdAt: datetime
    updatedAt: datetime


class RiskNotificationResponse(BaseModel):
    """Clean business payload used for the initial Teams notification."""
    riskId: str
    title: str
    vessel: Vessel
    severity: Severity
    summary: str
    deadline: date
    actions: list[ActionButton]


class RiskDetailsResponse(BaseModel):
    riskId: str
    title: str
    fundingShortfall: int
    paymentsAtRisk: int
    deadline: date
    accountRisk: str
    underlyingExposure: list[str]
    impact: list[str]


class MitigationPlanResponse(BaseModel):
    riskId: str
    title: str
    summary: str
    steps: list[MitigationStep]
