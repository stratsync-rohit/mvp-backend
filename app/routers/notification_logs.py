"""Read-only endpoints for inspecting notification/action logs."""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_notification_log_service
from app.schemas.notification_log import NotificationLogResponse
from app.services.notification_log_service import NotificationLogService
from app.utils.serializers import strip_mongo_id, strip_mongo_id_list

router = APIRouter(prefix="/api/notification-logs", tags=["Notification Logs"])

LogServiceDep = Annotated[NotificationLogService, Depends(get_notification_log_service)]


@router.get(
    "",
    response_model=list[NotificationLogResponse],
    summary="List notification logs",
    description="List notification/action logs with optional filters.",
)
async def list_logs(
    service: LogServiceDep,
    riskId: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    eventType: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    skip: int = Query(default=0, ge=0),
) -> list[dict]:
    logs = await service.list_logs(
        risk_id=riskId, status=status, event_type=eventType, limit=limit, skip=skip
    )
    return strip_mongo_id_list(logs)


@router.get(
    "/{eventId}",
    response_model=NotificationLogResponse,
    summary="Get a notification log by eventId",
)
async def get_log(eventId: str, service: LogServiceDep) -> dict:
    log = await service.get_log(eventId)
    return strip_mongo_id(log)
