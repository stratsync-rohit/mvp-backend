"""Strict risk envelope with extensible, JSON-safe business content."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.utils.route_keys import normalize_route_key

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Entity(StrictModel):
    type: str
    id: str
    name: str
    data: dict[str, Any] = Field(default_factory=dict)


class Metric(StrictModel):
    key: str
    label: str
    value: Any
    status: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class DynamicSection(BaseModel):
    """Known section identity plus arbitrary future section-specific fields."""
    model_config = ConfigDict(extra="allow")

    type: str
    title: str | None = None


class SectionCollection(StrictModel):
    sections: list[DynamicSection] = Field(default_factory=list)


class Tracking(StrictModel):
    enabled: bool = False
    trackedBy: str | None = None
    trackedAt: datetime | None = None


class Assignment(StrictModel):
    assignedTo: str | None = None
    assignedBy: str | None = None
    assignedAt: datetime | None = None


class RiskCreate(StrictModel):
    riskId: str
    accountId: str
    notificationRoute: str | None = None
    title: str
    severity: str
    status: str = "open"
    summary: str | None = None
    entity: Entity
    metrics: list[Metric] = Field(default_factory=list)
    details: SectionCollection = Field(default_factory=SectionCollection)
    mitigation: SectionCollection = Field(default_factory=SectionCollection)
    metadata: dict[str, Any] = Field(default_factory=dict)
    extensions: dict[str, Any] = Field(default_factory=dict)
    tracking: Tracking = Field(default_factory=Tracking)
    assignment: Assignment = Field(default_factory=Assignment)

    @field_validator("notificationRoute")
    @classmethod
    def validate_notification_route(cls, value: str | None) -> str | None:
        return normalize_route_key(value) if value is not None else None


class RiskUpdate(StrictModel):
    """PATCH fields; riskId/createdAt/updatedAt are deliberately unavailable."""
    title: str | None = None
    severity: str | None = None
    status: str | None = None
    summary: str | None = None
    entity: Entity | None = None
    metrics: list[Metric] | None = None
    details: SectionCollection | None = None
    mitigation: SectionCollection | None = None
    metadata: dict[str, Any] | None = None
    extensions: dict[str, Any] | None = None
    tracking: Tracking | None = None
    assignment: Assignment | None = None
    notificationRoute: str | None = None

    @field_validator("notificationRoute")
    @classmethod
    def validate_notification_route(cls, value: str | None) -> str | None:
        return normalize_route_key(value) if value is not None else None


class RiskResponse(RiskCreate):
    createdAt: datetime
    updatedAt: datetime


class RiskNotificationResponse(StrictModel):
    """Stable generic projection used by the initial Teams notification."""
    riskId: str
    title: str
    severity: str
    status: str
    summary: str
    entity: Entity
    metrics: list[Metric] = Field(default_factory=list)


class RiskSectionsResponse(StrictModel):
    riskId: str
    title: str
    sections: list[DynamicSection] = Field(default_factory=list)
