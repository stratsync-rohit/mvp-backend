"""Persistence for Teams app installations detected by the bot."""
from datetime import datetime, timezone
from typing import Any, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase


class TeamsInstallationRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._collection = db.teams_installations

    async def upsert(self, fields: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        key = {
            "accountId": fields["accountId"],
            "tenantId": fields["tenantId"],
            ("teamId" if fields.get("teamId") else "conversationId"): (
                fields.get("teamId") or fields["conversationId"]
            ),
        }
        await self._collection.update_one(
            key,
            {
                "$set": {**fields, "updatedAt": now},
                "$setOnInsert": {"createdAt": now},
            },
            upsert=True,
        )
        return await self._collection.find_one(key)

    async def get_active(self, account_id: str) -> Optional[dict[str, Any]]:
        return await self._collection.find_one(
            {"accountId": account_id, "enabled": True}, sort=[("updatedAt", -1)]
        )

    async def list_by_account(self, account_id: str) -> list[dict[str, Any]]:
        cursor = self._collection.find({"accountId": account_id}).sort("updatedAt", -1)
        return [document async for document in cursor]
