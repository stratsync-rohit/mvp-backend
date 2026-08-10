"""Repository for the `notification_logs` collection."""
from datetime import datetime, timezone
from typing import Any, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase


class NotificationLogRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._collection = db.notification_logs

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    async def create_pending(self, log_doc: dict[str, Any]) -> dict[str, Any]:
        log_doc = {**log_doc, "status": "pending", "createdAt": self._now()}
        await self._collection.insert_one(log_doc)
        return log_doc

    async def mark_success(self, event_id: str, n8n_response: dict[str, Any]) -> None:
        await self._collection.update_one(
            {"eventId": event_id},
            {"$set": {"status": "success", "n8nResponse": n8n_response, "errorMessage": None}},
        )

    async def mark_failed(self, event_id: str, error_message: str) -> None:
        await self._collection.update_one(
            {"eventId": event_id},
            {"$set": {"status": "failed", "errorMessage": error_message}},
        )

    async def get_by_event_id(self, event_id: str) -> Optional[dict[str, Any]]:
        return await self._collection.find_one({"eventId": event_id})

    async def list(
        self,
        risk_id: Optional[str] = None,
        status: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {}
        if risk_id:
            query["riskId"] = risk_id
        if status:
            query["status"] = status
        if event_type:
            query["eventType"] = event_type

        cursor = (
            self._collection.find(query)
            .sort("createdAt", -1)
            .skip(skip)
            .limit(limit)
        )
        return [doc async for doc in cursor]
