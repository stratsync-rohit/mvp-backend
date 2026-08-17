"""Persistence for Teams app installations detected by the bot."""
from datetime import datetime, timezone
from typing import Any, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument
from bson import ObjectId


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
                    "disconnectReason": None,
                    "disconnectSource": None,
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
        elif conversation_id:
            query["conversationId"] = conversation_id
        now = datetime.now(timezone.utc)
        return await self._collection.find_one_and_update(
            query,
            {"$set": {
                "enabled": False, "disconnectReason": "bot_uninstalled",
                "disconnectSource": "microsoft_teams", "disconnectedAt": now,
                "updatedAt": now,
            }},
            return_document=ReturnDocument.AFTER,
        )

    async def get_active(self, account_id: str) -> Optional[dict[str, Any]]:
        return await self._collection.find_one(
            {"accountId": account_id, "enabled": True}, sort=[("updatedAt", -1)]
        )

    async def get_active_by_team(
        self, account_id: str, tenant_id: str, team_id: str
    ) -> Optional[dict[str, Any]]:
        return await self._collection.find_one(
            {
                "accountId": account_id,
                "tenantId": tenant_id,
                "teamId": team_id,
                "enabled": True,
            },
            sort=[("updatedAt", -1)],
        )

    async def get_active_by_route(
        self, account_id: str, route_key: str
    ) -> Optional[dict[str, Any]]:
        return await self._collection.find_one(
            {"accountId": account_id, "routeKey": route_key, "enabled": True}
        )

    async def get_by_id(
        self, account_id: str, installation_id: str
    ) -> Optional[dict[str, Any]]:
        if not ObjectId.is_valid(installation_id):
            return None
        return await self._collection.find_one(
            {"_id": ObjectId(installation_id), "accountId": account_id}
        )

    async def assign_route(
        self, account_id: str, installation_id: str, route_key: str
    ) -> Optional[dict[str, Any]]:
        if not ObjectId.is_valid(installation_id):
            return None
        now = datetime.now(timezone.utc)
        return await self._collection.find_one_and_update(
            {"_id": ObjectId(installation_id), "accountId": account_id},
            {"$set": {"routeKey": route_key, "updatedAt": now}},
            return_document=ReturnDocument.AFTER,
        )

    async def list_by_account(self, account_id: str) -> list[dict[str, Any]]:
        cursor = self._collection.find({"accountId": account_id}).sort("updatedAt", -1)
        return [document async for document in cursor]

    async def list_active_by_account(self, account_id: str) -> list[dict[str, Any]]:
        cursor = self._collection.find(
            {"accountId": account_id, "enabled": True}
        ).sort("updatedAt", -1)
        return [document async for document in cursor]
