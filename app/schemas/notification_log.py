"""Pydantic v2 schemas for notification logs."""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel

from app.models.risk import EventType, LogStatus


class NotificationLogResponse(BaseModel):
    eventId: str
    riskId: str
    eventType: EventType
    actionKey: Optional[str] = None
    accountId: str
    teamId: str
    channelId: str
    status: LogStatus
    n8nResponse: dict[str, Any] = {}
    errorMessage: Optional[str] = None
    createdAt: datetime
