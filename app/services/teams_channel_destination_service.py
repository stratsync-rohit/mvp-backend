"""Account-safe registration and resolution for Teams channel destinations."""
from typing import Any

from app.exceptions.handlers import (
    MicrosoftTenantMappingDisabledError,
    MicrosoftTenantNotMappedError,
    TeamsChannelDestinationNotFoundError,
    TeamsInstallationUnavailableError,
)
from app.repositories.teams_channel_destination_repository import (
    TeamsChannelDestinationRepository,
)
from app.repositories.tenant_mapping_repository import TenantMappingRepository
from app.schemas.teams import TeamsChannelDestinationCreate
from app.utils.logger import get_logger

logger = get_logger(__name__)


class TeamsChannelDestinationService:
    def __init__(
        self,
        repository: TeamsChannelDestinationRepository,
        tenant_mapping_repository: TenantMappingRepository,
    ):
        self._repo = repository
        self._tenant_mapping_repo = tenant_mapping_repository

    async def register(self, payload: TeamsChannelDestinationCreate) -> dict[str, Any]:
        fields = payload.model_dump(mode="json", exclude_none=True)
        mapping = await self._tenant_mapping_repo.get_by_tenant(fields["tenantId"])
        if not mapping:
            raise MicrosoftTenantNotMappedError()
        if not mapping.get("enabled", False):
            raise MicrosoftTenantMappingDisabledError()

        scoped = {"accountId": mapping["accountId"], **fields}
        previous = await self._repo.get_matching(scoped)
        destination = await self._repo.upsert(scoped)
        event = "teams_destination_created"
        if previous:
            event = (
                "teams_destination_reactivated"
                if not previous.get("enabled", False)
                else "teams_destination_updated"
            )
        logger.info(event, extra={
            "accountId": mapping["accountId"],
            "tenantId": fields["tenantId"],
            "teamId": fields["teamId"],
            "channelId": fields["channelId"],
        })
        return destination

    async def list_by_account(self, account_id: str) -> list[dict[str, Any]]:
        return await self._repo.list_by_account(account_id)

    async def list_safe_by_account(self, account_id: str) -> list[dict[str, Any]]:
        return [
            {
                "destinationId": str(item["_id"]),
                "teamName": item.get("teamName"),
                "channelName": item.get("channelName"),
                "connected": item.get("enabled", False) is True,
            }
            for item in await self._repo.list_by_account(account_id)
        ]

    async def resolve_selected(
        self, account_id: str, destination_id: str
    ) -> dict[str, Any]:
        destination = await self._repo.get_by_id(account_id, destination_id)
        if not destination:
            raise TeamsChannelDestinationNotFoundError()
        if not destination.get("enabled", False):
            raise TeamsInstallationUnavailableError()
        return destination

    async def disable_team(
        self, account_id: str, tenant_id: str, team_id: str
    ) -> int:
        count = await self._repo.disable_by_team(account_id, tenant_id, team_id)
        if count:
            logger.info("teams_destination_disabled", extra={
                "accountId": account_id,
                "tenantId": tenant_id,
                "teamId": team_id,
            })
        return count
