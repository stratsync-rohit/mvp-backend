"""Pydantic v2 schemas for Teams destinations and Send-to-Teams flow."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator, field_validator


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
    connectedByName: Optional[str] = None
    connectedById: Optional[str] = None
    connectedByAadObjectId: Optional[str] = None
    botAppId: str
    enabled: bool = True


class TeamsInstallationResponse(TeamsInstallationCreate):
    installationId: str
    accountId: str
    routeKey: Optional[str] = None
    createdAt: datetime
    updatedAt: datetime
    connectedAt: Optional[datetime] = None
    disconnectedAt: Optional[datetime] = None


class TeamsInstallationSummary(BaseModel):
    """Browser-safe installation projection for one selected account."""
    installationId: str
    teamName: Optional[str] = None
    channelName: Optional[str] = None
    connected: bool
    enabled: bool
    connectedAt: Optional[datetime] = None
    disconnectedAt: Optional[datetime] = None


class TeamsChannelDestinationCreate(BaseModel):
    tenantId: str = Field(min_length=1)
    teamId: str = Field(min_length=1)
    teamName: Optional[str] = None
    channelId: str = Field(min_length=1)
    channelName: Optional[str] = None
    conversationId: str = Field(min_length=1)
    serviceUrl: str = Field(min_length=1)
    connectedByName: Optional[str] = None


class TeamsChannelDestinationResponse(TeamsChannelDestinationCreate):
    destinationId: str
    accountId: str
    enabled: bool
    createdAt: datetime
    updatedAt: datetime
    connectedAt: datetime
    disconnectedAt: Optional[datetime] = None


class TeamsChannelDestinationRegistrationResponse(BaseModel):
    success: bool
    destination: TeamsChannelDestinationResponse


class TeamsChannelDestinationSummary(BaseModel):
    destinationId: str
    teamName: Optional[str] = None
    channelName: Optional[str] = None
    connected: bool
    disconnectReason: Optional[str] = None
    disconnectedAt: Optional[datetime] = None


class TeamsChannelDestinationDisconnectResponse(BaseModel):
    success: bool
    destinationId: str
    connected: bool
    message: str


class TeamsInstallationRegistrationResponse(BaseModel):
    success: bool
    message: str
    installation: TeamsInstallationResponse


class TeamsInstallationDisconnect(BaseModel):
    tenantId: str = Field(min_length=1)
    teamId: Optional[str] = None
    conversationId: Optional[str] = None

    @model_validator(mode="after")
    def require_installation_identity(self):
        if not self.teamId and not self.conversationId:
            raise ValueError("teamId or conversationId is required")
        return self


class TeamsInstallationDisconnectResponse(BaseModel):
    success: bool
    disconnected: bool
    message: str
    accountId: str


class TeamsInstallationRouteUpdate(BaseModel):
    routeKey: str

    @field_validator("routeKey")
    @classmethod
    def validate_route_key(cls, value: str) -> str:
        from app.utils.route_keys import normalize_route_key

        return normalize_route_key(value)


class TeamsIntegrationOverviewItem(BaseModel):
    accountId: str
    accountName: str
    tenantId: str
    connected: bool
    activeInstallations: int
    teamName: Optional[str] = None
    channelName: Optional[str] = None
    connectedByName: Optional[str] = None
    updatedAt: datetime


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
    accountName: Optional[str] = None
    tenantId: Optional[str] = None
    teamId: Optional[str] = None
    channelId: Optional[str] = None
    conversationId: Optional[str] = None
    teamName: Optional[str] = None
    channelName: Optional[str] = None
    connectedByName: Optional[str] = None
    enabled: bool


class SendToTeamsRequest(BaseModel):
    requestedBy: Optional[str] = None
    installationId: Optional[str] = Field(default=None, min_length=1)
    destinationId: Optional[str] = Field(default=None, min_length=1)

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
