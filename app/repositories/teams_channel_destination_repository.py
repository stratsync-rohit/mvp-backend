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
                    "disconnectReason": None,
                    "disconnectSource": None,
                    "lastDeliveryErrorAt": None,
                    "lastDeliveryErrorCode": None,
                    "consecutiveDeliveryFailures": 0,
                    "updatedAt": now,
                },
                "$setOnInsert": {"createdAt": now},
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )

    async def repair_channel_conversation(
        self, account_id: str, destination_id: str, channel_id: str
    ) -> Optional[dict[str, Any]]:
        if not ObjectId.is_valid(destination_id):
            return None
        now = datetime.now(timezone.utc)
        return await self._collection.find_one_and_update(
            {
                "_id": ObjectId(destination_id),
                "accountId": account_id,
                "channelId": channel_id,
            },
            {"$set": {"conversationId": channel_id, "updatedAt": now}},
            return_document=ReturnDocument.AFTER,
        )

    async def list_by_account(self, account_id: str) -> list[dict[str, Any]]:
        cursor = self._collection.find({"accountId": account_id}).sort("updatedAt", -1)
        return [item async for item in cursor]

    async def list_active_by_account(self, account_id: str) -> list[dict[str, Any]]:
        cursor = self._collection.find({
            "accountId": account_id,
            "enabled": True,
            "disconnectedAt": None,
        }).sort("updatedAt", -1)
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
            {"$set": {
                "enabled": False, "disconnectReason": "team_uninstalled",
                "disconnectSource": "microsoft_teams", "disconnectedAt": now,
                "updatedAt": now,
            }},
        )
        return result.modified_count

    async def disable_by_channel(
        self,
        account_id: str,
        tenant_id: str,
        team_id: str,
        channel_id: str,
    ) -> int:
        now = datetime.now(timezone.utc)
        result = await self._collection.update_one(
            {
                "accountId": account_id,
                "tenantId": tenant_id,
                "teamId": team_id,
                "channelId": channel_id,
                "enabled": True,
            },
            {"$set": {
                "enabled": False, "disconnectReason": "channel_removed",
                "disconnectSource": "microsoft_teams", "disconnectedAt": now,
                "updatedAt": now,
            }},
        )
        return result.modified_count

    async def disconnect_manual(
        self, account_id: str, destination_id: str
    ) -> Optional[dict[str, Any]]:
        if not ObjectId.is_valid(destination_id):
            return None
        now = datetime.now(timezone.utc)
        return await self._collection.find_one_and_update(
            {"_id": ObjectId(destination_id), "accountId": account_id},
            {"$set": {
                "enabled": False, "disconnectReason": "manual_removal",
                "disconnectSource": "stratsync_ui", "disconnectedAt": now,
                "updatedAt": now,
            }},
            return_document=ReturnDocument.AFTER,
        )

    async def record_delivery_result(
        self,
        account_id: str,
        destination_id: str,
        *,
        error_code: str | None = None,
        disconnect_reason: str | None = None,
    ) -> Optional[dict[str, Any]]:
        if not ObjectId.is_valid(destination_id):
            return None
        now = datetime.now(timezone.utc)
        update: dict[str, Any]
        if error_code is None:
            update = {"$set": {
                "lastDeliveryErrorAt": None, "lastDeliveryErrorCode": None,
                "consecutiveDeliveryFailures": 0, "updatedAt": now,
            }}
        else:
            fields: dict[str, Any] = {
                "lastDeliveryErrorAt": now, "lastDeliveryErrorCode": error_code,
                "updatedAt": now,
            }
            if disconnect_reason:
                fields.update({
                    "enabled": False, "disconnectReason": disconnect_reason,
                    "disconnectSource": "microsoft_teams", "disconnectedAt": now,
                })
            update = {"$set": fields, "$inc": {"consecutiveDeliveryFailures": 1}}
        return await self._collection.find_one_and_update(
            {"_id": ObjectId(destination_id), "accountId": account_id},
            update, return_document=ReturnDocument.AFTER,
        )
