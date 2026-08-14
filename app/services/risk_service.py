"""
Risk service - business logic for risk CRUD and derived payloads
(notification / details / mitigation-plan projections).
"""
from typing import Any, Optional

from app.exceptions.handlers import RiskAlreadyExistsError, RiskNotFoundError
from app.repositories.risk_repository import RiskRepository
from app.schemas.risk import RiskCreate, RiskUpdate
from app.services.risk_normalizer import normalize_risk_document
from app.utils.logger import get_logger

logger = get_logger(__name__)


class RiskService:
    def __init__(self, risk_repository: RiskRepository):
        self._repo = risk_repository

    async def create_risk(self, account_id: str, payload: RiskCreate) -> dict[str, Any]:
        if await self._repo.exists(account_id, payload.riskId):
            raise RiskAlreadyExistsError()

        doc = payload.model_dump(mode="json")
        doc["accountId"] = account_id
        # Store deadline as ISO date string, matching the example doc shape.
        return normalize_risk_document(await self._repo.create(doc))

    async def list_risks(
        self,
        account_id: str,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> list[dict[str, Any]]:
        documents = await self._repo.list(
            severity=severity, status=status, account_id=account_id, limit=limit, skip=skip
        )
        return [normalize_risk_document(document) for document in documents]

    async def get_risk(self, account_id: str, risk_id: str) -> dict[str, Any]:
        risk = await self._repo.get_by_id(account_id, risk_id)
        if not risk:
            logger.warning("risk_not_found_for_account", extra={"accountId": account_id, "riskId": risk_id})
            raise RiskNotFoundError(risk_id)
        return normalize_risk_document(risk)

    async def update_risk(self, account_id: str, risk_id: str, payload: RiskUpdate) -> dict[str, Any]:
        # Ensure it exists first so we can return a clean 404.
        await self.get_risk(account_id, risk_id)

        update_fields = payload.model_dump(mode="json", exclude_unset=True, exclude_none=True)
        updated = await self._repo.update(account_id, risk_id, update_fields)
        if not updated:
            raise RiskNotFoundError(risk_id)
        return normalize_risk_document(updated)

    async def delete_risk(self, account_id: str, risk_id: str) -> None:
        deleted = await self._repo.delete(account_id, risk_id)
        if not deleted:
            raise RiskNotFoundError(risk_id)

    async def get_notification_payload(self, account_id: str, risk_id: str) -> dict[str, Any]:
        """Clean business payload for the initial Teams notification."""
        risk = await self.get_risk(account_id, risk_id)
        return {
            "riskId": risk["riskId"],
            "title": risk["title"],
            "severity": risk["severity"],
            "status": risk["status"],
            "summary": risk.get("summary") or "",
            "entity": risk["entity"],
            "metrics": risk["metrics"],
        }

    async def get_details_payload(self, account_id: str, risk_id: str) -> dict[str, Any]:
        risk = await self.get_risk(account_id, risk_id)
        return {
            "riskId": risk["riskId"],
            "title": risk["title"],
            "sections": risk["details"]["sections"],
        }

    async def get_details_action_payload(self, account_id: str, risk_id: str) -> dict[str, Any]:
        """Projection used only by the view_details action card."""
        risk = await self.get_risk(account_id, risk_id)
        return {
            "title": "Risk Details",
            "subtitle": risk["title"],
            "severity": risk["severity"],
            "entity": risk["entity"],
            "sections": risk["details"]["sections"],
        }

    async def get_mitigation_plan_payload(self, account_id: str, risk_id: str) -> dict[str, Any]:
        risk = await self.get_risk(account_id, risk_id)
        return {
            "riskId": risk["riskId"],
            "title": risk["title"],
            "sections": risk["mitigation"]["sections"],
        }

    async def get_mitigation_plan_action_payload(self, account_id: str, risk_id: str) -> dict[str, Any]:
        """Projection used only by the mitigation_plan action card."""
        risk = await self.get_risk(account_id, risk_id)
        return {
            "title": "Mitigation Plan",
            "subtitle": risk["title"],
            "severity": risk["severity"],
            "entity": risk["entity"],
            "sections": risk["mitigation"]["sections"],
        }

    async def set_tracking(self, account_id: str, risk_id: str, tracked_by: Optional[str]) -> dict[str, Any]:
        await self.get_risk(account_id, risk_id)
        updated = await self._repo.set_tracking(account_id, risk_id, tracked_by)
        if not updated:
            raise RiskNotFoundError(risk_id)
        return updated

    async def set_assignment(
        self, account_id: str, risk_id: str, assigned_to: str, assigned_by: str
    ) -> dict[str, Any]:
        await self.get_risk(account_id, risk_id)
        updated = await self._repo.set_assignment(account_id, risk_id, assigned_to, assigned_by)
        if not updated:
            raise RiskNotFoundError(risk_id)
        return updated
