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
        return await self.get_by_id(risk_doc["accountId"], risk_doc["riskId"])

    async def _backfill_legacy_timestamps(self, risk_doc: dict[str, Any]) -> dict[str, Any]:
        """Lazily add root timestamps required by the API to legacy documents."""
        missing: dict[str, datetime] = {}
        created_at = risk_doc.get("createdAt")
        updated_at = risk_doc.get("updatedAt")

        if created_at is None:
            object_id = risk_doc.get("_id")
            created_at = updated_at or getattr(object_id, "generation_time", None) or self._now()
            missing["createdAt"] = created_at
        if updated_at is None:
            updated_at = created_at
            missing["updatedAt"] = updated_at

        if missing:
            await self._collection.update_one({"_id": risk_doc["_id"]}, {"$set": missing})
            risk_doc.update(missing)
        return risk_doc

    async def get_by_id(self, account_id: str, risk_id: str) -> Optional[dict[str, Any]]:
        risk_doc = await self._collection.find_one(
            {"accountId": account_id, "riskId": risk_id}
        )
        if risk_doc is None:
            return None
        return await self._backfill_legacy_timestamps(risk_doc)

    async def exists(self, account_id: str, risk_id: str) -> bool:
        count = await self._collection.count_documents(
            {"accountId": account_id, "riskId": risk_id}, limit=1
        )
        return count > 0

    async def list(
        self,
        account_id: str,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {"accountId": account_id}
        if severity:
            query["severity"] = severity
        if status:
            query["status"] = status
        cursor = (
            self._collection.find(query)
            .sort("createdAt", -1)
            .skip(skip)
            .limit(limit)
        )
        return [await self._backfill_legacy_timestamps(doc) async for doc in cursor]

    async def update(self, account_id: str, risk_id: str, update_fields: dict[str, Any]) -> Optional[dict[str, Any]]:
        update_fields = dict(update_fields)
        update_fields["updatedAt"] = self._now()
        update_fields.pop("riskId", None)
        update_fields.pop("createdAt", None)
        update_fields.pop("accountId", None)

        await self._collection.update_one(
            {"accountId": account_id, "riskId": risk_id}, {"$set": update_fields}
        )
        return await self.get_by_id(account_id, risk_id)

    async def delete(self, account_id: str, risk_id: str) -> bool:
        result = await self._collection.delete_one(
            {"accountId": account_id, "riskId": risk_id}
        )
        return result.deleted_count > 0

    async def set_tracking(self, account_id: str, risk_id: str, tracked_by: Optional[str]) -> Optional[dict[str, Any]]:
        now = self._now()
        await self._collection.update_one(
            {"accountId": account_id, "riskId": risk_id},
            {
                "$set": {
                    "tracking.enabled": True,
                    "tracking.trackedBy": tracked_by,
                    "tracking.trackedAt": now,
                    "updatedAt": now,
                }
            },
        )
        return await self.get_by_id(account_id, risk_id)

    async def set_assignment(
        self, account_id: str, risk_id: str, assigned_to: str, assigned_by: str
    ) -> Optional[dict[str, Any]]:
        now = self._now()
        await self._collection.update_one(
            {"accountId": account_id, "riskId": risk_id},
            {
                "$set": {
                    "assignment.assignedTo": assigned_to,
                    "assignment.assignedBy": assigned_by,
                    "assignment.assignedAt": now,
                    "updatedAt": now,
                }
            },
        )
        return await self.get_by_id(account_id, risk_id)
