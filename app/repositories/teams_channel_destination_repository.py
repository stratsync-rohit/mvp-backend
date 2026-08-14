"""Persistence for independently addressable Microsoft Teams channels."""
from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument


class TeamsChannelDestinationRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._collection = db.teams_channel_destinations

    async def get_matching(self, fields: dict[str, Any]) -> Optional[dict[str, Any]]:
        return await self._collection.find_one({
            "accountId": fields["accountId"],
            "tenantId": fields["tenantId"],
            "teamId": fields["teamId"],
            "channelId": fields["channelId"],
        })

    async def upsert(self, fields: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        key = {
            "accountId": fields["accountId"],
            "tenantId": fields["tenantId"],
            "teamId": fields["teamId"],
            "channelId": fields["channelId"],
        }
        return await self._collection.find_one_and_update(
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
            return_document=ReturnDocument.AFTER,
        )

    async def list_by_account(self, account_id: str) -> list[dict[str, Any]]:
        cursor = self._collection.find({"accountId": account_id}).sort("updatedAt", -1)
        return [item async for item in cursor]

    async def get_by_id(
        self, account_id: str, destination_id: str
    ) -> Optional[dict[str, Any]]:
        if not ObjectId.is_valid(destination_id):
            return None
        return await self._collection.find_one({
            "_id": ObjectId(destination_id), "accountId": account_id,
        })

    async def disable_by_team(
        self, account_id: str, tenant_id: str, team_id: str
    ) -> int:
        now = datetime.now(timezone.utc)
        result = await self._collection.update_many(
            {
                "accountId": account_id,
                "tenantId": tenant_id,
                "teamId": team_id,
                "enabled": True,
            },
            {"$set": {"enabled": False, "disconnectedAt": now, "updatedAt": now}},
        )
        return result.modified_count
