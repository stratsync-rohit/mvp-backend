"""
Risk service - business logic for risk CRUD and derived payloads
(notification / details / mitigation-plan projections).
"""
from typing import Any, Optional

from app.exceptions.handlers import RiskAlreadyExistsError, RiskNotFoundError
from app.models.risk import DEFAULT_ACTIONS
from app.repositories.risk_repository import RiskRepository
from app.schemas.risk import RiskCreate, RiskUpdate
from app.services.risk_normalizer import normalize_risk_document


class RiskService:
    def __init__(self, risk_repository: RiskRepository):
        self._repo = risk_repository

    async def create_risk(self, payload: RiskCreate) -> dict[str, Any]:
        if await self._repo.exists(payload.riskId):
            raise RiskAlreadyExistsError()

        doc = payload.model_dump(mode="json")
        # Store deadline as ISO date string, matching the example doc shape.
        return normalize_risk_document(await self._repo.create(doc))

    async def list_risks(
        self,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        account_id: Optional[str] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> list[dict[str, Any]]:
        documents = await self._repo.list(
            severity=severity, status=status, account_id=account_id, limit=limit, skip=skip
        )
        return [normalize_risk_document(document) for document in documents]

    async def get_risk(self, risk_id: str) -> dict[str, Any]:
        risk = await self._repo.get_by_risk_id(risk_id)
        if not risk:
            raise RiskNotFoundError(risk_id)
        return normalize_risk_document(risk)

    async def update_risk(self, risk_id: str, payload: RiskUpdate) -> dict[str, Any]:
        # Ensure it exists first so we can return a clean 404.
        await self.get_risk(risk_id)

        update_fields = payload.model_dump(mode="json", exclude_unset=True, exclude_none=True)
        updated = await self._repo.update(risk_id, update_fields)
        if not updated:
            raise RiskNotFoundError(risk_id)
        return normalize_risk_document(updated)

    async def delete_risk(self, risk_id: str) -> None:
        deleted = await self._repo.delete(risk_id)
        if not deleted:
            raise RiskNotFoundError(risk_id)

    async def get_notification_payload(self, risk_id: str) -> dict[str, Any]:
        """Clean business payload for the initial Teams notification."""
        risk = await self.get_risk(risk_id)
        entity = risk["entity"]
        legacy = risk.get("extensions", {}).get("legacy", {})
        result = {
            "riskId": risk["riskId"],
            "title": risk["title"],
            "entity": entity,
            # Compatibility adapter: the deployed bot reads vessel.id/name.
            "vessel": {"id": entity["id"], "name": entity["name"]},
            "severity": risk["severity"],
            "summary": risk["summary"],
            "actions": DEFAULT_ACTIONS,
        }
        if legacy.get("deadline"):
            result["deadline"] = legacy["deadline"]
        return result

    async def get_details_payload(self, risk_id: str) -> dict[str, Any]:
        risk = await self.get_risk(risk_id)
        return {
            "riskId": risk["riskId"],
            "title": risk["title"],
            "sections": risk["details"]["sections"],
        }

    async def get_details_action_payload(self, risk_id: str) -> dict[str, Any]:
        """Projection used only by the view_details action card."""
        risk = await self.get_risk(risk_id)
        return {
            "title": "Risk Details",
            "subtitle": risk["title"],
            "severity": risk["severity"],
            "entity": risk["entity"],
            "sections": risk["details"]["sections"],
        }

    async def get_mitigation_plan_payload(self, risk_id: str) -> dict[str, Any]:
        risk = await self.get_risk(risk_id)
        return {
            "riskId": risk["riskId"],
            "title": risk["title"],
            "sections": risk["mitigation"]["sections"],
        }

    async def get_mitigation_plan_action_payload(self, risk_id: str) -> dict[str, Any]:
        """Projection used only by the mitigation_plan action card."""
        risk = await self.get_risk(risk_id)
        return {
            "title": "Mitigation Plan",
            "subtitle": risk["title"],
            "severity": risk["severity"],
            "entity": risk["entity"],
            "sections": risk["mitigation"]["sections"],
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
