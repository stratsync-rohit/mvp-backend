"""Account-safe registration and resolution for Teams channel destinations."""
from typing import Any

from app.exceptions.handlers import (
    MicrosoftTenantMappingDisabledError,
    MicrosoftTenantNotMappedError,
    TeamsChannelDestinationNotFoundError,
    TeamsChannelDestinationReconnectConflictError,
    TeamsInstallationUnavailableError,
    TeamsInstallationNotConfiguredError,
    TeamsRouteRequiredError,
)
from app.repositories.teams_channel_destination_repository import (
    TeamsChannelDestinationRepository,
)
from app.repositories.tenant_mapping_repository import TenantMappingRepository
from app.repositories.teams_installation_repository import TeamsInstallationRepository
from app.schemas.teams import TeamsChannelDestinationCreate
from app.utils.logger import get_logger

logger = get_logger(__name__)


class TeamsChannelDestinationService:
    def __init__(
        self,
        repository: TeamsChannelDestinationRepository,
        tenant_mapping_repository: TenantMappingRepository,
        installation_repository: TeamsInstallationRepository,
    ):
        self._repo = repository
        self._tenant_mapping_repo = tenant_mapping_repository
        self._installation_repo = installation_repository

    async def register(self, payload: TeamsChannelDestinationCreate) -> dict[str, Any]:
        registration_trigger = payload.registrationTrigger
        fields = payload.model_dump(mode="json", exclude_none=True)
        for metadata_field in ("teamName", "channelName", "connectedByName"):
            if not fields.get(metadata_field):
                fields.pop(metadata_field, None)
        mapping = await self._tenant_mapping_repo.get_by_tenant(fields["tenantId"])
        if not mapping:
            logger.warning("teams_tenant_account_resolution_failed", extra={
                "tenantId": fields["tenantId"], "result": "not_mapped",
            })
            raise MicrosoftTenantNotMappedError()
        if not mapping.get("enabled", False):
            logger.warning("teams_tenant_account_resolution_failed", extra={
                "tenantId": fields["tenantId"], "accountId": mapping["accountId"],
                "result": "disabled",
            })
            raise MicrosoftTenantMappingDisabledError()

        logger.info("teams_tenant_account_resolved", extra={
            "tenantId": fields["tenantId"], "accountId": mapping["accountId"],
            "result": "resolved",
        })

        scoped = {"accountId": mapping["accountId"], **fields}
        if scoped.get("teamName"):
            logger.info("teams_team_metadata_resolved", extra={
                "tenantId": fields["tenantId"],
                "teamId": fields["teamId"],
                "channelId": fields["channelId"],
                "resolutionSource": "channel_activity",
            })
        else:
            installation = await self._installation_repo.get_by_team(
                mapping["accountId"], fields["tenantId"], fields["teamId"]
            )
            if installation and installation.get("teamName"):
                scoped["teamName"] = installation["teamName"]
                logger.info("teams_channel_destination_enriched", extra={
                    "tenantId": fields["tenantId"],
                    "teamId": fields["teamId"],
                    "channelId": fields["channelId"],
                    "resolutionSource": "team_installation",
                })
            else:
                logger.info("teams_team_metadata_missing", extra={
                    "tenantId": fields["tenantId"],
                    "teamId": fields["teamId"],
                    "channelId": fields["channelId"],
                    "resolutionSource": "not_available",
                })
        previous = await self._repo.get_matching(scoped)
        if (
            previous
            and previous.get("disconnectReason") == "manual_removal"
            and registration_trigger not in {"explicit_connect", "explicit_reconnect"}
        ):
            logger.info("teams_channel_destination_registration_skipped", extra={
                "accountId": mapping["accountId"],
                "tenantId": fields["tenantId"],
                "teamId": fields["teamId"],
                "channelId": fields["channelId"],
                "destinationId": str(previous["_id"]),
                "registrationTrigger": registration_trigger,
                "reason": "manual_removal",
            })
            return previous
        destination = await self._repo.upsert(scoped)
        event = "teams_destination_created"
        if previous:
            event = (
                "teams_destination_reactivated"
                if not previous.get("enabled", False)
                else "teams_destination_updated"
            )
        logger.info("teams_channel_destination_registered", extra={
            "accountId": mapping["accountId"],
            "tenantId": fields["tenantId"],
            "teamId": fields["teamId"],
            "channelId": fields["channelId"],
            "destinationId": str(destination["_id"]),
            "operation": event,
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
                "disconnectReason": item.get("disconnectReason"),
                "disconnectedAt": item.get("disconnectedAt"),
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
        if destination.get("disconnectedAt") is not None:
            raise TeamsInstallationUnavailableError()
        required = ("tenantId", "teamId", "channelId", "conversationId", "serviceUrl")
        if any(not destination.get(field) for field in required):
            raise TeamsChannelDestinationNotFoundError()
        if destination["conversationId"] != destination["channelId"]:
            raise TeamsChannelDestinationNotFoundError()
        return destination

    async def resolve_default(self, account_id: str) -> dict[str, Any]:
        """Backward-compatible fallback only when exactly one channel is active."""
        destinations = await self._repo.list_active_by_account(account_id)
        if not destinations:
            raise TeamsInstallationNotConfiguredError()
        if len(destinations) > 1:
            raise TeamsRouteRequiredError()
        destination = destinations[0]
        required = ("tenantId", "teamId", "channelId", "conversationId", "serviceUrl")
        if any(not destination.get(field) for field in required):
            raise TeamsChannelDestinationNotFoundError()
        if destination["conversationId"] != destination["channelId"]:
            raise TeamsChannelDestinationNotFoundError()
        return destination

    async def disconnect(self, account_id: str, destination_id: str) -> dict[str, Any]:
        existing = await self._repo.get_by_id(account_id, destination_id)
        if not existing:
            raise TeamsChannelDestinationNotFoundError()
        destination = await self._repo.disconnect_manual(account_id, destination_id)
        if not destination:
            raise TeamsInstallationUnavailableError()
        logger.info("teams_channel_destination_disconnected", extra={
            "accountId": account_id, "destinationId": destination_id,
            "teamId": destination.get("teamId"),
            "channelId": destination.get("channelId"),
        })
        return {
            "success": True, "destinationId": destination_id,
            "destination": destination,
            "message": "Teams channel disconnected successfully",
        }

    async def reconnect(self, account_id: str, destination_id: str) -> dict[str, Any]:
        existing = await self._repo.get_by_id(account_id, destination_id)
        if not existing:
            raise TeamsChannelDestinationNotFoundError()
        destination = await self._repo.reconnect_manual(account_id, destination_id)
        if not destination:
            raise TeamsChannelDestinationReconnectConflictError()
        logger.info("teams_channel_destination_reconnected", extra={
            "accountId": account_id, "destinationId": destination_id,
            "teamId": destination.get("teamId"),
            "channelId": destination.get("channelId"),
        })
        return {
            "success": True, "destinationId": destination_id,
            "destination": destination,
            "message": "Teams channel reconnected successfully",
        }

    async def record_delivery_result(
        self, account_id: str, destination_id: str, result: dict[str, Any]
    ) -> None:
        # Legacy n8n workflows return {status: ...}; any response that does not
        # explicitly report failure is a successful delivery acknowledgement.
        if result.get("success") is not False:
            await self._repo.record_delivery_result(account_id, destination_id)
            return
        code = result.get("errorCode")
        if not isinstance(code, str):
            code = "unknown_error"
        permanent_reasons = {
            "conversation_not_found": "channel_deleted",
            "channel_not_found": "channel_deleted",
            "bot_not_in_conversation": "channel_unavailable",
            "permission_revoked": "permission_revoked",
        }
        reason = permanent_reasons.get(code) if result.get("retryable") is False else None
        await self._repo.record_delivery_result(
            account_id, destination_id, error_code=code, disconnect_reason=reason,
        )

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

    async def disable_channel(
        self, account_id: str, tenant_id: str, team_id: str, channel_id: str
    ) -> int:
        count = await self._repo.disable_by_channel(
            account_id, tenant_id, team_id, channel_id
        )
        if count:
            logger.info("teams_channel_destination_disabled", extra={
                "accountId": account_id, "tenantId": tenant_id,
                "teamId": team_id, "channelId": channel_id,
            })
        return count
