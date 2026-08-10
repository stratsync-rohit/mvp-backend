"""Repository for the `teams_destinations` collection."""
from datetime import datetime, timezone
from typing import Any, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase


class TeamsDestinationRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._collection = db.teams_destinations

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    async def upsert(self, account_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        now = self._now()
        await self._collection.update_one(
            {"accountId": account_id},
            {
                "$set": {**fields, "updatedAt": now},
                "$setOnInsert": {"accountId": account_id, "createdAt": now},
            },
            upsert=True,
        )
        return await self.get_by_account_id(account_id)

    async def get_by_account_id(self, account_id: str) -> Optional[dict[str, Any]]:
        return await self._collection.find_one({"accountId": account_id})

    async def list(self) -> list[dict[str, Any]]:
        cursor = self._collection.find({}).sort("accountId", 1)
        return [doc async for doc in cursor]
