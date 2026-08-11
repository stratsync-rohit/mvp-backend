"""Business operations for Teams app installations."""
from typing import Any

from app.exceptions.handlers import MicrosoftTenantNotMappedError, TeamsInstallationNotConfiguredError
from app.repositories.tenant_mapping_repository import TenantMappingRepository
from app.repositories.teams_installation_repository import TeamsInstallationRepository
from app.schemas.teams import TeamsInstallationCreate


class TeamsInstallationService:
    def __init__(
        self,
        repository: TeamsInstallationRepository,
        tenant_mapping_repository: TenantMappingRepository,
    ):
        self._repo = repository
        self._tenant_mapping_repo = tenant_mapping_repository

    async def register(self, payload: TeamsInstallationCreate) -> dict[str, Any]:
        fields = payload.model_dump(mode="json")
        mapping = await self._tenant_mapping_repo.get_enabled_by_tenant(fields["tenantId"])
        if not mapping:
            raise MicrosoftTenantNotMappedError()
        return await self._repo.upsert({"accountId": mapping["accountId"], **fields})

    async def get_active(self, account_id: str) -> dict[str, Any]:
        installation = await self._repo.get_active(account_id)
        if not installation:
            raise TeamsInstallationNotConfiguredError()
        return installation

    async def integration_status(self, account_id: str) -> dict[str, Any]:
        installation = await self._repo.get_active(account_id)
        if not installation:
            return {"connected": False, "accountId": account_id, "enabled": False}
        return {
            "connected": True,
            "accountId": account_id,
            "tenantId": installation["tenantId"],
            "teamId": installation.get("teamId"),
            "channelId": installation.get("channelId"),
            "conversationId": installation["conversationId"],
            "teamName": installation.get("teamName"),
            "channelName": installation.get("channelName"),
            "enabled": True,
        }

    async def list_by_account(self, account_id: str) -> list[dict[str, Any]]:
        return await self._repo.list_by_account(account_id)
