"""Business operations for Microsoft tenant mappings."""
from typing import Any

from app.exceptions.handlers import TenantMappingNotFoundError
from app.repositories.tenant_mapping_repository import TenantMappingRepository
from app.schemas.teams import TenantMappingCreate


class TenantMappingService:
    def __init__(self, repository: TenantMappingRepository):
        self._repo = repository

    async def upsert(self, account_id: str, payload: TenantMappingCreate) -> dict[str, Any]:
        return await self._repo.upsert(account_id, payload.model_dump(mode="json"))

    async def get_by_account(self, account_id: str) -> dict[str, Any]:
        mapping = await self._repo.get_by_account(account_id)
        if not mapping:
            raise TenantMappingNotFoundError()
        return mapping

    async def get_by_tenant(self, tenant_id: str) -> dict[str, Any]:
        mapping = await self._repo.get_by_tenant(tenant_id)
        if not mapping:
            raise TenantMappingNotFoundError()
        return mapping
