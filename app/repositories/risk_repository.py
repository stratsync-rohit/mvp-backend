"""
Risk repository - the ONLY place that talks to the `risks` MongoDB collection.

Routers and services never touch Motor/PyMongo directly for risks; they go
through this repository.
"""
from datetime import datetime, timezone
from typing import Any, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase


class RiskRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._collection = db.risks

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    async def create(self, risk_doc: dict[str, Any]) -> dict[str, Any]:
        now = self._now()
        risk_doc = {**risk_doc, "createdAt": now, "updatedAt": now}
        await self._collection.insert_one(risk_doc)
        return await self.get_by_risk_id(risk_doc["riskId"])

    async def get_by_risk_id(self, risk_id: str) -> Optional[dict[str, Any]]:
        return await self._collection.find_one({"riskId": risk_id})

    async def exists(self, risk_id: str) -> bool:
        count = await self._collection.count_documents({"riskId": risk_id}, limit=1)
        return count > 0

    async def list(
        self,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        account_id: Optional[str] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {}
        if severity:
            query["severity"] = severity
        if status:
            query["status"] = status
        if account_id:
            query["accountId"] = account_id

        cursor = (
            self._collection.find(query)
            .sort("createdAt", -1)
            .skip(skip)
            .limit(limit)
        )
        return [doc async for doc in cursor]

    async def update(self, risk_id: str, update_fields: dict[str, Any]) -> Optional[dict[str, Any]]:
        if not update_fields:
            return await self.get_by_risk_id(risk_id)

        update_fields["updatedAt"] = self._now()
        # riskId must never be changed via update
        update_fields.pop("riskId", None)

        await self._collection.update_one({"riskId": risk_id}, {"$set": update_fields})
        return await self.get_by_risk_id(risk_id)

    async def delete(self, risk_id: str) -> bool:
        result = await self._collection.delete_one({"riskId": risk_id})
        return result.deleted_count > 0

    async def set_tracking(self, risk_id: str, tracked_by: Optional[str]) -> Optional[dict[str, Any]]:
        now = self._now()
        await self._collection.update_one(
            {"riskId": risk_id},
            {
                "$set": {
                    "tracking.enabled": True,
                    "tracking.trackedBy": tracked_by,
                    "tracking.trackedAt": now,
                    "updatedAt": now,
                }
            },
        )
        return await self.get_by_risk_id(risk_id)

    async def set_assignment(
        self, risk_id: str, assigned_to: str, assigned_by: str
    ) -> Optional[dict[str, Any]]:
        now = self._now()
        await self._collection.update_one(
            {"riskId": risk_id},
            {
                "$set": {
                    "assignment.assignedTo": assigned_to,
                    "assignment.assignedBy": assigned_by,
                    "assignment.assignedAt": now,
                    "updatedAt": now,
                }
            },
        )
        return await self.get_by_risk_id(risk_id)
