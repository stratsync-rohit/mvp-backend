"""Pydantic v2 schemas for risk-action execution."""
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.risk import ActionKey
from app.schemas.risk import DynamicSection, Entity


class AssignActionPayload(BaseModel):
    assignedTo: str
    assignedBy: str


class RiskActionRequest(BaseModel):
    riskId: str
    tenantId: str = Field(min_length=1)
    actionKey: ActionKey
    payload: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_payload_for_action(self) -> "RiskActionRequest":
        if self.actionKey == ActionKey.ASSIGN:
            if not self.payload:
                raise ValueError("payload with assignedTo/assignedBy is required for 'assign'")
            AssignActionPayload.model_validate(self.payload)
        return self


class DynamicCardData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    subtitle: str | None = None
    severity: str
    entity: Entity
    sections: list[DynamicSection] = Field(default_factory=list)


class RiskActionResponse(BaseModel):
    success: bool = True
    riskId: str
    actionKey: ActionKey
    cardType: str
    data: DynamicCardData


class RiskActionAckResponse(BaseModel):
    success: bool
    riskId: str
    actionKey: ActionKey
    message: str
