"""
Action service - handles POST /api/risk-actions/execute.

Uses a handler-mapping pattern (rather than if/elif chains in the router)
so each action is isolated, testable, and easy to extend.
"""
from typing import Any, Awaitable, Callable

from app.models.risk import ActionKey
from app.schemas.actions import RiskActionRequest
from app.services.risk_service import RiskService
from app.repositories.tenant_mapping_repository import TenantMappingRepository
from app.exceptions.handlers import MicrosoftTenantNotMappedError

HandlerType = Callable[[RiskActionRequest, str], Awaitable[dict[str, Any]]]


class ActionService:
    def __init__(self, risk_service: RiskService, tenant_mapping_repository: TenantMappingRepository):
        self._risk_service = risk_service
        self._tenant_mapping_repo = tenant_mapping_repository
        self._handlers: dict[ActionKey, HandlerType] = {
            ActionKey.VIEW_DETAILS: self._handle_view_details,
            ActionKey.MITIGATION_PLAN: self._handle_mitigation_plan,
            ActionKey.TRACK_RISK: self._handle_track_risk,
            ActionKey.ASSIGN: self._handle_assign,
        }

    async def execute(self, request: RiskActionRequest) -> dict[str, Any]:
        mapping = await self._tenant_mapping_repo.get_enabled_by_tenant(request.tenantId)
        if not mapping:
            raise MicrosoftTenantNotMappedError()
        account_id = mapping["accountId"]
        await self._risk_service.get_risk(account_id, request.riskId)

        handler = self._handlers[request.actionKey]
        return await handler(request, account_id)

    # -- Handlers -----------------------------------------------------------

    async def _handle_view_details(self, request: RiskActionRequest, account_id: str) -> dict[str, Any]:
        data = await self._risk_service.get_details_action_payload(account_id, request.riskId)
        return {
            "success": True,
            "riskId": request.riskId,
            "actionKey": ActionKey.VIEW_DETAILS.value,
            "cardType": "dynamic_card",
            "data": data,
        }

    async def _handle_mitigation_plan(self, request: RiskActionRequest, account_id: str) -> dict[str, Any]:
        data = await self._risk_service.get_mitigation_plan_action_payload(account_id, request.riskId)
        return {
            "success": True,
            "riskId": request.riskId,
            "actionKey": ActionKey.MITIGATION_PLAN.value,
            "cardType": "dynamic_card",
            "data": data,
        }

    async def _handle_track_risk(self, request: RiskActionRequest, account_id: str) -> dict[str, Any]:
        payload = request.payload or {}
        tracked_by = payload.get("actorName") or payload.get("actorId")
        await self._risk_service.set_tracking(account_id, request.riskId, tracked_by)
        return {
            "success": True,
            "riskId": request.riskId,
            "actionKey": ActionKey.TRACK_RISK.value,
            "message": "Risk tracking enabled",
        }

    async def _handle_assign(self, request: RiskActionRequest, account_id: str) -> dict[str, Any]:
        payload = request.payload or {}
        assigned_to = payload["assignedTo"]
        assigned_by = payload["assignedBy"]
        await self._risk_service.set_assignment(account_id, request.riskId, assigned_to, assigned_by)
        return {
            "success": True,
            "riskId": request.riskId,
            "actionKey": ActionKey.ASSIGN.value,
            "message": f"Risk assigned to {assigned_to}",
        }
