"""Pydantic v2 schemas for Teams destinations and Send-to-Teams flow."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class TeamDestinationCreate(BaseModel):
    teamId: str
    channelId: str
    teamName: str
    channelName: str
    enabled: bool = True


class TeamDestinationResponse(BaseModel):
    accountId: str
    teamId: str
    channelId: str
    teamName: str
    channelName: str
    enabled: bool
    createdAt: datetime
    updatedAt: datetime


class SendToTeamsRequest(BaseModel):
    requestedBy: Optional[str] = None

    @field_validator("requestedBy")
    @classmethod
    def validate_email_ish(cls, v: Optional[str]) -> Optional[str]:
        # Kept permissive (not a hard EmailStr) since this is optional metadata,
        # but we do a light sanity check.
        if v is not None and "@" not in v:
            raise ValueError("requestedBy should look like an email address")
        return v


class SendToTeamsResponse(BaseModel):
    success: bool
    eventId: str
    riskId: str
    message: str
