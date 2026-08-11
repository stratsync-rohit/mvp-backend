"""
Risk service - business logic for risk CRUD and derived payloads
(notification / details / mitigation-plan projections).
"""
from typing import Any, Optional

from app.exceptions.handlers import RiskAlreadyExistsError, RiskNotFoundError
from app.models.risk import DEFAULT_ACTIONS
from app.repositories.risk_repository import RiskRepository
from app.schemas.risk import RiskCreate, RiskUpdate


class RiskService:
    def __init__(self, risk_repository: RiskRepository):
        self._repo = risk_repository

    async def create_risk(self, payload: RiskCreate) -> dict[str, Any]:
        if await self._repo.exists(payload.riskId):
            raise RiskAlreadyExistsError()

        doc = payload.model_dump(mode="json")
        # Store deadline as ISO date string, matching the example doc shape.
        return await self._repo.create(doc)

    async def list_risks(
        self,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        account_id: Optional[str] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> list[dict[str, Any]]:
        return await self._repo.list(
            severity=severity, status=status, account_id=account_id, limit=limit, skip=skip
        )

    async def get_risk(self, risk_id: str) -> dict[str, Any]:
        risk = await self._repo.get_by_risk_id(risk_id)
        if not risk:
            raise RiskNotFoundError(risk_id)
        return risk

    async def update_risk(self, risk_id: str, payload: RiskUpdate) -> dict[str, Any]:
        # Ensure it exists first so we can return a clean 404.
        await self.get_risk(risk_id)

        update_fields = payload.model_dump(mode="json", exclude_unset=True, exclude_none=True)
        updated = await self._repo.update(risk_id, update_fields)
        if not updated:
            raise RiskNotFoundError(risk_id)
        return updated

    async def delete_risk(self, risk_id: str) -> None:
        deleted = await self._repo.delete(risk_id)
        if not deleted:
            raise RiskNotFoundError(risk_id)

    async def get_notification_payload(self, risk_id: str) -> dict[str, Any]:
        """Clean business payload for the initial Teams notification."""
        risk = await self.get_risk(risk_id)
        return {
            "riskId": risk["riskId"],
            "title": risk["title"],
            "vessel": risk["vessel"],
            "severity": risk["severity"],
            "summary": risk["summary"],
            "deadline": risk["deadline"],
            "actions": DEFAULT_ACTIONS,
        }

    async def get_details_payload(self, risk_id: str) -> dict[str, Any]:
        risk = await self.get_risk(risk_id)
        details = risk.get("details", {}) or {}
        return {
            "riskId": risk["riskId"],
            "title": risk["title"],
            "fundingShortfall": risk.get("fundingShortfall", 0),
            "paymentsAtRisk": risk.get("paymentsAtRisk", 0),
            "deadline": risk["deadline"],
            "accountRisk": risk.get("accountRisk", ""),
            "underlyingExposure": details.get("underlyingExposure", []),
            "impact": details.get("impact", []),
        }

    async def get_details_action_payload(self, risk_id: str) -> dict[str, Any]:
        """Projection used only by the view_details action card."""
        risk = await self.get_risk(risk_id)
        details = risk.get("details", {}) or {}
        return {
            "title": risk["title"],
            "severity": risk["severity"],
            "vessel": risk["vessel"],
            "summary": risk["summary"],
            "details": {
                "underlyingExposure": details.get("underlyingExposure", []),
                "impact": details.get("impact", []),
            },
        }

    async def get_mitigation_plan_payload(self, risk_id: str) -> dict[str, Any]:
        risk = await self.get_risk(risk_id)
        plan = risk.get("mitigationPlan", {}) or {}
        return {
            "riskId": risk["riskId"],
            "title": risk["title"],
            "summary": plan.get("summary") or "",
            "steps": plan.get("steps", []),
        }

    async def get_mitigation_plan_action_payload(self, risk_id: str) -> dict[str, Any]:
        """Projection used only by the mitigation_plan action card."""
        risk = await self.get_risk(risk_id)
        plan = risk.get("mitigationPlan", {}) or {}
        return {
            "title": risk["title"],
            "severity": risk["severity"],
            "vessel": risk["vessel"],
            "mitigationPlan": {
                "summary": plan.get("summary"),
                "steps": plan.get("steps", []),
                "lastUpdated": plan.get("lastUpdated"),
            },
        }

    async def set_tracking(self, risk_id: str, tracked_by: Optional[str]) -> dict[str, Any]:
        await self.get_risk(risk_id)
        updated = await self._repo.set_tracking(risk_id, tracked_by)
        if not updated:
            raise RiskNotFoundError(risk_id)
        return updated

    async def set_assignment(
        self, risk_id: str, assigned_to: str, assigned_by: str
    ) -> dict[str, Any]:
        await self.get_risk(risk_id)
        updated = await self._repo.set_assignment(risk_id, assigned_to, assigned_by)
        if not updated:
            raise RiskNotFoundError(risk_id)
        return updated
