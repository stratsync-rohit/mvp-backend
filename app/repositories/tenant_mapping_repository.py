"""Persistence for Microsoft tenant to StratSync account mappings."""
from datetime import datetime, timezone
from typing import Any, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument


class TenantMappingRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._collection = db.tenant_mappings
        self._counters = db.counters

    async def upsert(self, account_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        await self._collection.update_one(
            {"accountId": account_id},
            {
                "$set": {"accountId": account_id, **fields, "updatedAt": now},
                "$setOnInsert": {"createdAt": now},
            },
            upsert=True,
        )
        return await self._collection.find_one({"accountId": account_id})

    async def get_by_account(self, account_id: str) -> Optional[dict[str, Any]]:
        return await self._collection.find_one({"accountId": account_id})

    async def get_by_tenant(self, tenant_id: str) -> Optional[dict[str, Any]]:
        return await self._collection.find_one({"tenantId": tenant_id})

    async def get_enabled_by_tenant(self, tenant_id: str) -> Optional[dict[str, Any]]:
        return await self._collection.find_one({"tenantId": tenant_id, "enabled": True})

    async def next_account_id(self) -> str:
        """Allocate an ACC-NNN ID from an atomic, existing-data-aware sequence."""
        max_sequence = 0
        cursor = self._collection.find(
            {"accountId": {"$regex": r"^ACC-[0-9]+$"}}, {"accountId": 1}
        )
        async for mapping in cursor:
            max_sequence = max(max_sequence, int(mapping["accountId"].split("-", 1)[1]))

        # $max makes initialization/reconciliation safe when multiple workers
        # start together or a higher ACC-* mapping was created administratively.
        await self._counters.update_one(
            {"_id": "account_id"},
            {"$max": {"sequence": max_sequence}},
            upsert=True,
        )
        counter = await self._counters.find_one_and_update(
            {"_id": "account_id"},
            {"$inc": {"sequence": 1}},
            return_document=ReturnDocument.AFTER,
        )
        return f"ACC-{counter['sequence']:03d}"

    async def create_provisioned(
        self, account_id: str, tenant_id: str, client_name: str
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        document = {
            "accountId": account_id,
            "clientName": client_name,
            "tenantId": tenant_id,
            "enabled": True,
            "createdAt": now,
            "updatedAt": now,
        }
        await self._collection.insert_one(document)
        return document

    async def list_all(self) -> list[dict[str, Any]]:
        cursor = self._collection.find({}).sort("accountId", 1)
        return [document async for document in cursor]

    async def list_account_metadata(self) -> list[dict[str, Any]]:
        """Read only fields safe for the browser-facing MVP selector."""
        cursor = self._collection.find(
            {"accountId": {"$type": "string"}},
            {"_id": 0, "accountId": 1, "clientName": 1},
        ).sort("accountId", 1)
        return [document async for document in cursor]
