"""Pydantic v2 schemas for the risk-actions execution flow."""
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator

from app.models.risk import ActionKey, Severity
from app.schemas.common import Vessel
from app.schemas.risk import MitigationPlan, RiskDetails


class AssignActionPayload(BaseModel):
    assignedTo: str
    assignedBy: str


class TrackActionPayload(BaseModel):
    actorId: Optional[str] = None
    actorName: Optional[str] = None


class RiskActionRequest(BaseModel):
    riskId: str
    actionKey: ActionKey
    payload: Optional[dict[str, Any]] = None

    @model_validator(mode="after")
    def validate_payload_for_action(self) -> "RiskActionRequest":
        if self.actionKey == ActionKey.ASSIGN:
            if not self.payload:
                raise ValueError("payload with assignedTo/assignedBy is required for 'assign'")
            # Validate shape without mutating self.payload type
            AssignActionPayload.model_validate(self.payload)
        return self


class RiskDetailsActionData(BaseModel):
    title: str
    severity: Severity
    vessel: Vessel
    summary: str
    details: RiskDetails = Field(default_factory=RiskDetails)


class MitigationPlanActionData(BaseModel):
    title: str
    severity: Severity
    vessel: Vessel
    mitigationPlan: MitigationPlan = Field(default_factory=MitigationPlan)


class RiskActionResponse(BaseModel):
    """Standard envelope for read-only card actions."""
    success: bool = True
    riskId: str
    actionKey: ActionKey
    cardType: str
    data: RiskDetailsActionData | MitigationPlanActionData


class RiskActionAckResponse(BaseModel):
    """Envelope for state-mutating actions like track_risk / assign."""
    success: bool
    riskId: str
    actionKey: ActionKey
    message: str
