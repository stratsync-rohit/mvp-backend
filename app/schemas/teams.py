"""Pydantic v2 schemas for Teams destinations and Send-to-Teams flow."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


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


class TeamsInstallationCreate(BaseModel):
    tenantId: str = Field(min_length=1)
    teamId: Optional[str] = None
    channelId: Optional[str] = None
    conversationId: str = Field(min_length=1)
    serviceUrl: str = Field(min_length=1)
    teamName: Optional[str] = None
    channelName: Optional[str] = None
    botAppId: str
    enabled: bool = True


class TeamsInstallationResponse(TeamsInstallationCreate):
    accountId: str
    createdAt: datetime
    updatedAt: datetime


class TeamsInstallationRegistrationResponse(BaseModel):
    success: bool
    message: str
    installation: TeamsInstallationResponse


class TenantMappingCreate(BaseModel):
    tenantId: str = Field(min_length=1)
    clientName: str = Field(min_length=1)
    enabled: bool = True


class TenantMappingResponse(TenantMappingCreate):
    accountId: str
    createdAt: datetime
    updatedAt: datetime


class TenantMappingUpsertResponse(BaseModel):
    success: bool
    mapping: TenantMappingResponse


class TeamsIntegrationStatus(BaseModel):
    connected: bool
    accountId: str
    tenantId: Optional[str] = None
    teamId: Optional[str] = None
    channelId: Optional[str] = None
    conversationId: Optional[str] = None
    teamName: Optional[str] = None
    channelName: Optional[str] = None
    enabled: bool


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
