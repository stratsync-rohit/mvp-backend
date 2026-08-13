"""Persistence for Teams app installations detected by the bot."""
from datetime import datetime, timezone
from typing import Any, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument


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
                "$set": {
                    **fields,
                    "enabled": True,
                    "connectedAt": now,
                    "disconnectedAt": None,
                    "updatedAt": now,
                },
                "$setOnInsert": {"createdAt": now},
            },
            upsert=True,
        )
        return await self._collection.find_one(key)

    async def get_matching(self, fields: dict[str, Any]) -> Optional[dict[str, Any]]:
        key = {
            "accountId": fields["accountId"],
            "tenantId": fields["tenantId"],
            ("teamId" if fields.get("teamId") else "conversationId"): (
                fields.get("teamId") or fields["conversationId"]
            ),
        }
        return await self._collection.find_one(key)

    async def disconnect(
        self,
        account_id: str,
        tenant_id: str,
        team_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        query: dict[str, Any] = {
            "accountId": account_id,
            "tenantId": tenant_id,
            "enabled": True,
        }
        if team_id:
            query["teamId"] = team_id
        if conversation_id:
            query["conversationId"] = conversation_id
        now = datetime.now(timezone.utc)
        return await self._collection.find_one_and_update(
            query,
            {"$set": {"enabled": False, "disconnectedAt": now, "updatedAt": now}},
            return_document=ReturnDocument.AFTER,
        )

    async def get_active(self, account_id: str) -> Optional[dict[str, Any]]:
        return await self._collection.find_one(
            {"accountId": account_id, "enabled": True}, sort=[("updatedAt", -1)]
        )

    async def list_by_account(self, account_id: str) -> list[dict[str, Any]]:
        cursor = self._collection.find({"accountId": account_id}).sort("updatedAt", -1)
        return [document async for document in cursor]

    async def list_active_by_account(self, account_id: str) -> list[dict[str, Any]]:
        cursor = self._collection.find(
            {"accountId": account_id, "enabled": True}
        ).sort("updatedAt", -1)
        return [document async for document in cursor]
