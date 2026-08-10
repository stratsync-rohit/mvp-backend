"""
Risk CRUD + derived payload endpoints.

Routers contain NO database logic - everything is delegated to
RiskService, which in turn delegates persistence to RiskRepository.
"""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header, Query, status

from app.dependencies import get_notification_service, get_risk_service
from app.schemas.common import DeleteRiskResponse
from app.schemas.risk import (
    MitigationPlanResponse,
    RiskCreate,
    RiskDetailsResponse,
    RiskNotificationResponse,
    RiskResponse,
    RiskUpdate,
)
from app.schemas.teams import SendToTeamsRequest, SendToTeamsResponse
from app.services.notification_service import NotificationService
from app.services.risk_service import RiskService
from app.utils.serializers import strip_mongo_id, strip_mongo_id_list

router = APIRouter(prefix="/api/risks", tags=["Risks"])

RiskServiceDep = Annotated[RiskService, Depends(get_risk_service)]
NotificationServiceDep = Annotated[NotificationService, Depends(get_notification_service)]


@router.post(
    "",
    response_model=RiskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a risk",
    description="Creates a new risk. riskId must be unique (returns 409 if it already exists).",
)
async def create_risk(payload: RiskCreate, service: RiskServiceDep) -> dict:
    created = await service.create_risk(payload)
    return strip_mongo_id(created)


@router.get(
    "",
    response_model=list[RiskResponse],
    summary="List risks",
    description="List risks with optional filtering by severity, status, and accountId.",
)
async def list_risks(
    service: RiskServiceDep,
    severity: Optional[str] = Query(default=None),
    status_: Optional[str] = Query(default=None, alias="status"),
    accountId: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    skip: int = Query(default=0, ge=0),
) -> list[dict]:
    risks = await service.list_risks(
        severity=severity, status=status_, account_id=accountId, limit=limit, skip=skip
    )
    return strip_mongo_id_list(risks)


@router.get(
    "/{riskId}",
    response_model=RiskResponse,
    summary="Get a risk",
    description="Fetch the latest risk data by riskId. Returns 404 if not found.",
)
async def get_risk(riskId: str, service: RiskServiceDep) -> dict:
    risk = await service.get_risk(riskId)
    return strip_mongo_id(risk)


@router.patch(
    "/{riskId}",
    response_model=RiskResponse,
    summary="Update a risk",
    description="Partial update of a risk. riskId itself cannot be changed.",
)
async def update_risk(riskId: str, payload: RiskUpdate, service: RiskServiceDep) -> dict:
    updated = await service.update_risk(riskId, payload)
    return strip_mongo_id(updated)


@router.delete(
    "/{riskId}",
    response_model=DeleteRiskResponse,
    summary="Delete a risk",
    description="Hard-deletes a risk (acceptable for the current testing system).",
)
async def delete_risk(riskId: str, service: RiskServiceDep) -> dict:
    await service.delete_risk(riskId)
    return {"success": True, "riskId": riskId}


@router.get(
    "/{riskId}/notification",
    response_model=RiskNotificationResponse,
    summary="Initial notification payload",
    description=(
        "Clean business payload for the initial Teams notification. "
        "Does NOT include Adaptive Card JSON - the Teams Bot service renders that."
    ),
)
async def get_notification_payload(riskId: str, service: RiskServiceDep) -> dict:
    return await service.get_notification_payload(riskId)


@router.get(
    "/{riskId}/details",
    response_model=RiskDetailsResponse,
    summary="View Details payload",
    description="Business data backing the Teams 'View Details' button.",
)
async def get_details(riskId: str, service: RiskServiceDep) -> dict:
    return await service.get_details_payload(riskId)


@router.get(
    "/{riskId}/mitigation-plan",
    response_model=MitigationPlanResponse,
    summary="Mitigation Plan payload",
    description="Business data backing the Teams 'Mitigation Plan' button.",
)
async def get_mitigation_plan(riskId: str, service: RiskServiceDep) -> dict:
    return await service.get_mitigation_plan_payload(riskId)


@router.post(
    "/{riskId}/send-to-teams",
    response_model=SendToTeamsResponse,
    summary="Send risk notification to Microsoft Teams",
    description=(
        "Loads the latest risk from MongoDB, resolves the Teams destination for its "
        "accountId, and triggers the n8n notification webhook. The frontend should send "
        "only riskId - never the full risk object."
    ),
)
async def send_to_teams(
    riskId: str,
    service: NotificationServiceDep,
    payload: SendToTeamsRequest | None = None,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> dict:
    requested_by = payload.requestedBy if payload else None
    return await service.send_to_teams(
        risk_id=riskId, requested_by=requested_by, idempotency_key=idempotency_key
    )
