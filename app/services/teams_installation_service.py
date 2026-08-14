"""Business operations for Teams app installations."""
from typing import Any

from app.exceptions.handlers import (
    MicrosoftTenantMappingDisabledError,
    MicrosoftTenantNotMappedError,
    TeamsInstallationNotFoundError,
    TeamsInstallationNotConfiguredError,
    TeamsInstallationUnavailableError,
    TeamsRouteConflictError,
    TeamsRouteNotConfiguredError,
    TeamsRouteRequiredError,
)
from pymongo.errors import DuplicateKeyError
from app.repositories.tenant_mapping_repository import TenantMappingRepository
from app.repositories.teams_installation_repository import TeamsInstallationRepository
from app.schemas.teams import TeamsInstallationCreate, TeamsInstallationDisconnect
from app.services.teams_channel_destination_service import TeamsChannelDestinationService
from app.utils.logger import get_logger

logger = get_logger(__name__)


class TeamsInstallationService:
    def __init__(
        self,
        repository: TeamsInstallationRepository,
        tenant_mapping_repository: TenantMappingRepository,
        channel_destination_service: TeamsChannelDestinationService,
    ):
        self._repo = repository
        self._tenant_mapping_repo = tenant_mapping_repository
        self._channel_destination_service = channel_destination_service

    async def register(self, payload: TeamsInstallationCreate) -> dict[str, Any]:
        # Sparse lifecycle events must not erase useful metadata captured by
        # an earlier event for the same installation.
        fields = payload.model_dump(mode="json", exclude_none=True)
        mapping = await self.resolve_or_provision_account(
            tenant_id=fields["tenantId"],
            team_name=fields.get("teamName"),
            connected_by_name=fields.get("connectedByName"),
        )
        scoped_fields = {"accountId": mapping["accountId"], **fields}
        previous = await self._repo.get_matching(scoped_fields)
        try:
            installation = await self._repo.upsert(scoped_fields)
        except DuplicateKeyError as exc:
            # A historical routed installation may be reactivated only when
            # another active destination has not claimed that account route.
            raise TeamsRouteConflictError() from exc
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

    async def resolve_or_provision_account(
        self,
        tenant_id: str,
        team_name: str | None = None,
        connected_by_name: str | None = None,
    ) -> dict[str, Any]:
        """Resolve tenant ownership, provisioning it once when it is new.

        ``team_name`` is only a provisional display-name fallback. Actor names
        are deliberately not used as customer names.
        """
        mapping = await self._tenant_mapping_repo.get_by_tenant(tenant_id)
        if mapping:
            if not mapping.get("enabled", False):
                logger.warning(
                    "teams_tenant_mapping_disabled",
                    extra={"tenantId": tenant_id, "accountId": mapping["accountId"]},
                )
                raise MicrosoftTenantMappingDisabledError()
            logger.info(
                "teams_tenant_mapping_found",
                extra={"tenantId": tenant_id, "accountId": mapping["accountId"]},
            )
            return mapping

        logger.info(
            "teams_tenant_auto_provision_started",
            extra={"tenantId": tenant_id, "hasTeamName": bool(team_name)},
        )
        # Account-ID collisions can only occur if a legacy/manual writer races
        # the counter. Retrying preserves both uniqueness and tenant isolation.
        while True:
            account_id = await self._tenant_mapping_repo.next_account_id()
            try:
                mapping = await self._tenant_mapping_repo.create_provisioned(
                    account_id=account_id,
                    tenant_id=tenant_id,
                    client_name=team_name or account_id,
                )
            except DuplicateKeyError:
                mapping = await self._tenant_mapping_repo.get_by_tenant(tenant_id)
                if not mapping:
                    continue
                if not mapping.get("enabled", False):
                    logger.warning(
                        "teams_tenant_mapping_disabled",
                        extra={"tenantId": tenant_id, "accountId": mapping["accountId"]},
                    )
                    raise MicrosoftTenantMappingDisabledError()
                logger.info(
                    "teams_tenant_auto_provision_race_resolved",
                    extra={"tenantId": tenant_id, "accountId": mapping["accountId"]},
                )
                return mapping

            logger.info(
                "teams_tenant_auto_provisioned",
                extra={
                    "tenantId": tenant_id,
                    "accountId": account_id,
                    "hasTeamName": bool(team_name),
                },
            )
            return mapping

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
        if installation and installation.get("teamId"):
            await self._channel_destination_service.disable_team(
                account_id,
                payload.tenantId,
                installation["teamId"],
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
            logger.warning(
                "teams_destination_not_found_for_account",
                extra={"accountId": account_id},
            )
            raise TeamsInstallationNotConfiguredError()
        return installation

    async def resolve_active_destination(
        self, account_id: str, route_key: str | None = None
    ) -> dict[str, Any]:
        if route_key is not None:
            installation = await self._repo.get_active_by_route(account_id, route_key)
            if not installation:
                raise TeamsRouteNotConfiguredError(route_key)
            return installation

        active = await self._repo.list_active_by_account(account_id)
        if not active:
            raise TeamsInstallationNotConfiguredError()
        if len(active) > 1:
            raise TeamsRouteRequiredError()
        return active[0]

    async def resolve_selected_destination(
        self, account_id: str, installation_id: str
    ) -> dict[str, Any]:
        """Resolve an explicit browser selection within its trusted account scope."""
        installation = await self._repo.get_by_id(account_id, installation_id)
        if not installation:
            # The same response covers malformed, unknown, and cross-account IDs
            # without disclosing whether another account owns the identifier.
            raise TeamsInstallationNotFoundError()
        if not installation.get("enabled", False):
            raise TeamsInstallationUnavailableError()
        return installation

    async def assign_route(
        self, account_id: str, installation_id: str, route_key: str
    ) -> dict[str, Any]:
        try:
            installation = await self._repo.assign_route(
                account_id, installation_id, route_key
            )
        except DuplicateKeyError as exc:
            raise TeamsRouteConflictError() from exc
        if not installation:
            raise TeamsInstallationNotFoundError()
        return installation

    async def integration_status(self, account_id: str) -> dict[str, Any]:
        installation = await self._repo.get_active(account_id)
        mapping = await self._tenant_mapping_repo.get_by_account(account_id)
        logger.info(
            "teams_integration_status_checked",
            extra={"accountId": account_id, "connected": installation is not None},
        )
        if not installation:
            return {"connected": False, "accountId": account_id, "enabled": False}
        return {
            "connected": True,
            "accountId": account_id,
            "accountName": (
                mapping.get("clientName") if mapping else None
            ) or account_id,
            "tenantId": installation["tenantId"],
            "teamId": installation.get("teamId"),
            "channelId": installation.get("channelId"),
            "conversationId": installation["conversationId"],
            "teamName": installation.get("teamName"),
            "channelName": installation.get("channelName"),
            "connectedByName": installation.get("connectedByName"),
            "enabled": True,
        }

    async def list_by_account(self, account_id: str) -> list[dict[str, Any]]:
        return await self._repo.list_by_account(account_id)

    async def list_summaries_by_account(self, account_id: str) -> list[dict[str, Any]]:
        installations = await self._repo.list_by_account(account_id)
        return [
            {
                "installationId": str(item["_id"]),
                "teamName": item.get("teamName"),
                "channelName": item.get("channelName"),
                "connected": item.get("enabled", False) is True,
                "enabled": item.get("enabled", False) is True,
                "connectedAt": item.get("connectedAt"),
                "disconnectedAt": item.get("disconnectedAt"),
            }
            for item in installations
        ]

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
                    "channelName": latest.get("channelName") if latest else None,
                    "connectedByName": (
                        latest.get("connectedByName") if latest else None
                    ),
                    "updatedAt": (
                        latest.get("updatedAt") if latest else mapping["updatedAt"]
                    ),
                }
            )
        return result
