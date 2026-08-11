"""
Action service - handles POST /api/risk-actions/execute.

Uses a handler-mapping pattern (rather than if/elif chains in the router)
so each action is isolated, testable, and easy to extend.
"""
from typing import Any, Awaitable, Callable

from app.models.risk import ActionKey
from app.schemas.actions import RiskActionRequest
from app.services.risk_service import RiskService

HandlerType = Callable[[RiskActionRequest], Awaitable[dict[str, Any]]]


class ActionService:
    def __init__(self, risk_service: RiskService):
        self._risk_service = risk_service
        self._handlers: dict[ActionKey, HandlerType] = {
            ActionKey.VIEW_DETAILS: self._handle_view_details,
            ActionKey.MITIGATION_PLAN: self._handle_mitigation_plan,
            ActionKey.TRACK_RISK: self._handle_track_risk,
            ActionKey.ASSIGN: self._handle_assign,
        }

    async def execute(self, request: RiskActionRequest) -> dict[str, Any]:
        # Validates the risk exists up front (raises RiskNotFoundError otherwise).
        await self._risk_service.get_risk(request.riskId)

        handler = self._handlers[request.actionKey]
        return await handler(request)

    # -- Handlers -----------------------------------------------------------

    async def _handle_view_details(self, request: RiskActionRequest) -> dict[str, Any]:
        data = await self._risk_service.get_details_action_payload(request.riskId)
        return {
            "success": True,
            "riskId": request.riskId,
            "actionKey": ActionKey.VIEW_DETAILS.value,
            "cardType": "dynamic_card",
            "data": data,
        }

    async def _handle_mitigation_plan(self, request: RiskActionRequest) -> dict[str, Any]:
        data = await self._risk_service.get_mitigation_plan_action_payload(request.riskId)
        return {
            "success": True,
            "riskId": request.riskId,
            "actionKey": ActionKey.MITIGATION_PLAN.value,
            "cardType": "dynamic_card",
            "data": data,
        }

    async def _handle_track_risk(self, request: RiskActionRequest) -> dict[str, Any]:
        payload = request.payload or {}
        tracked_by = payload.get("actorName") or payload.get("actorId")
        await self._risk_service.set_tracking(request.riskId, tracked_by)
        return {
            "success": True,
            "riskId": request.riskId,
            "actionKey": ActionKey.TRACK_RISK.value,
            "message": "Risk tracking enabled",
        }

    async def _handle_assign(self, request: RiskActionRequest) -> dict[str, Any]:
        payload = request.payload or {}
        assigned_to = payload["assignedTo"]
        assigned_by = payload["assignedBy"]
        await self._risk_service.set_assignment(request.riskId, assigned_to, assigned_by)
        return {
            "success": True,
            "riskId": request.riskId,
            "actionKey": ActionKey.ASSIGN.value,
            "message": f"Risk assigned to {assigned_to}",
        }
