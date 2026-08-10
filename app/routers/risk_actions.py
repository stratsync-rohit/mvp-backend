"""
POST /api/risk-actions/execute

This is the reverse-flow entry point: the Teams bot (or n8n on its behalf)
calls this whenever a user clicks a button on an Adaptive Card.

Protected (optionally) by the internal API key dependency, since this
endpoint is meant to be called by trusted backend services, not browsers.
"""
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status

from app.dependencies import get_action_service, verify_internal_api_key
from app.models.risk import ActionKey
from app.schemas.actions import RiskActionAckResponse, RiskActionRequest, RiskActionResponse
from app.services.action_service import ActionService

router = APIRouter(prefix="/api/risk-actions", tags=["Risk Actions"])

ActionServiceDep = Annotated[ActionService, Depends(get_action_service)]

# Actions that mutate state and return a simple ack envelope vs. the
# {riskId, actionKey, cardType, data} envelope used for read-only actions.
_ACK_ACTIONS = {ActionKey.TRACK_RISK, ActionKey.ASSIGN}


@router.post(
    "/execute",
    response_model=RiskActionResponse | RiskActionAckResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute a risk action",
    description=(
        "Called by the Teams bot / n8n when a user clicks an Adaptive Card button "
        "(View Details, Mitigation Plan, Assign To, Track This Problem). "
        "Returns business data - the bot renders the resulting Adaptive Card."
    ),
    dependencies=[Depends(verify_internal_api_key)],
)
async def execute_action(request: RiskActionRequest, service: ActionServiceDep) -> dict[str, Any]:
    return await service.execute(request)
