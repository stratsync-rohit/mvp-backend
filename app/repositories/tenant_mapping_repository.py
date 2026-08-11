"""Persistence for Microsoft tenant to StratSync account mappings."""
from datetime import datetime, timezone
from typing import Any, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase


class TenantMappingRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._collection = db.tenant_mappings

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
