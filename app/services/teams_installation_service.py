"""Business operations for Teams app installations."""
from typing import Any

from app.exceptions.handlers import (
    MicrosoftTenantNotMappedError,
    TeamsInstallationNotConfiguredError,
)
from app.repositories.tenant_mapping_repository import TenantMappingRepository
from app.repositories.teams_installation_repository import TeamsInstallationRepository
from app.schemas.teams import TeamsInstallationCreate, TeamsInstallationDisconnect
from app.utils.logger import get_logger

logger = get_logger(__name__)


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
        scoped_fields = {"accountId": mapping["accountId"], **fields}
        previous = await self._repo.get_matching(scoped_fields)
        installation = await self._repo.upsert(scoped_fields)
        if previous and not previous.get("enabled", False):
            logger.info(
                "teams_installation_reactivated",
                extra={
                    "accountId": mapping["accountId"],
                    "tenantId": fields["tenantId"],
                    "teamId": fields.get("teamId"),
                },
            )
        return installation

    async def disconnect(self, payload: TeamsInstallationDisconnect) -> dict[str, Any]:
        mapping = await self._tenant_mapping_repo.get_enabled_by_tenant(payload.tenantId)
        if not mapping:
            raise MicrosoftTenantNotMappedError()
        account_id = mapping["accountId"]
        installation = await self._repo.disconnect(
            account_id=account_id,
            tenant_id=payload.tenantId,
            team_id=payload.teamId,
            conversation_id=payload.conversationId,
        )
        event = (
            "teams_installation_disconnected"
            if installation
            else "teams_installation_disconnect_not_found"
        )
        logger.info(
            event,
            extra={
                "accountId": account_id,
                "tenantId": payload.tenantId,
                "teamId": payload.teamId,
            },
        )
        return {
            "success": True,
            "disconnected": installation is not None,
            "message": (
                "Teams installation disconnected"
                if installation
                else "No matching active Teams installation found"
            ),
            "accountId": account_id,
        }

    async def get_active(self, account_id: str) -> dict[str, Any]:
        installation = await self._repo.get_active(account_id)
        if not installation:
            raise TeamsInstallationNotConfiguredError()
        return installation

    async def integration_status(self, account_id: str) -> dict[str, Any]:
        installation = await self._repo.get_active(account_id)
        logger.info(
            "teams_integration_status_checked",
            extra={"accountId": account_id, "connected": installation is not None},
        )
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

    async def integrations_overview(self) -> list[dict[str, Any]]:
        mappings = await self._tenant_mapping_repo.list_all()
        result = []
        for mapping in mappings:
            active = await self._repo.list_active_by_account(mapping["accountId"])
            latest = active[0] if active else None
            result.append(
                {
                    "accountId": mapping["accountId"],
                    "accountName": mapping.get("clientName") or mapping["accountId"],
                    "tenantId": mapping["tenantId"],
                    "connected": bool(active),
                    "activeInstallations": len(active),
                    "teamName": latest.get("teamName") if latest else None,
                    "updatedAt": (
                        latest.get("updatedAt") if latest else mapping["updatedAt"]
                    ),
                }
            )
        return result
