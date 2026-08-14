"""Teams destination mapping endpoints (accountId -> team/channel)."""
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.dependencies import (
    get_teams_destination_service,
    get_teams_channel_destination_service,
    get_teams_installation_service,
    get_tenant_mapping_service,
    verify_internal_api_key,
)
from app.schemas.teams import (
    TeamDestinationCreate,
    TeamDestinationResponse,
    TeamsChannelDestinationCreate,
    TeamsChannelDestinationRegistrationResponse,
    TeamsChannelDestinationResponse,
    TeamsChannelDestinationSummary,
    TeamsInstallationCreate,
    TeamsInstallationDisconnect,
    TeamsInstallationDisconnectResponse,
    TeamsInstallationRegistrationResponse,
    TeamsInstallationResponse,
    TeamsInstallationRouteUpdate,
    TeamsInstallationSummary,
    TeamsIntegrationOverviewItem,
    TeamsIntegrationStatus,
    TenantMappingCreate,
    TenantMappingResponse,
    TenantMappingUpsertResponse,
)
from app.services.teams_destination_service import TeamsDestinationService
from app.services.teams_channel_destination_service import TeamsChannelDestinationService
from app.services.teams_installation_service import TeamsInstallationService
from app.services.tenant_mapping_service import TenantMappingService
from app.utils.serializers import strip_mongo_id, strip_mongo_id_list

router = APIRouter(prefix="/api/teams", tags=["Teams Destinations"])


def serialize_installation(document: dict) -> dict:
    """Expose an opaque installation identifier, never MongoDB's raw `_id` field."""
    return {"installationId": str(document["_id"]), **strip_mongo_id(document)}


def serialize_channel_destination(document: dict) -> dict:
    return {"destinationId": str(document["_id"]), **strip_mongo_id(document)}


DestinationServiceDep = Annotated[TeamsDestinationService, Depends(get_teams_destination_service)]
ChannelDestinationServiceDep = Annotated[
    TeamsChannelDestinationService, Depends(get_teams_channel_destination_service)
]
InstallationServiceDep = Annotated[
    TeamsInstallationService, Depends(get_teams_installation_service)
]
TenantMappingServiceDep = Annotated[
    TenantMappingService, Depends(get_tenant_mapping_service)
]


@router.put(
    "/tenant-mappings/{accountId}",
    response_model=TenantMappingUpsertResponse,
)
async def upsert_tenant_mapping(
    accountId: str, payload: TenantMappingCreate, service: TenantMappingServiceDep
) -> dict:
    mapping = await service.upsert(accountId, payload)
    return {"success": True, "mapping": strip_mongo_id(mapping)}


@router.get(
    "/tenant-mappings/by-tenant/{tenantId}",
    response_model=TenantMappingResponse,
)
async def get_tenant_mapping_by_tenant(
    tenantId: str, service: TenantMappingServiceDep
) -> dict:
    return strip_mongo_id(await service.get_by_tenant(tenantId))


@router.get(
    "/tenant-mappings/{accountId}",
    response_model=TenantMappingResponse,
)
async def get_tenant_mapping(
    accountId: str, service: TenantMappingServiceDep
) -> dict:
    return strip_mongo_id(await service.get_by_account(accountId))


@router.post(
    "/installations",
    response_model=TeamsInstallationRegistrationResponse,
    dependencies=[Depends(verify_internal_api_key)],
)
async def register_installation(
    payload: TeamsInstallationCreate, service: InstallationServiceDep
) -> dict:
    installation = await service.register(payload)
    return {
        "success": True,
        "message": "Teams installation registered",
        "installation": serialize_installation(installation),
    }


@router.post(
    "/installations/disconnect",
    response_model=TeamsInstallationDisconnectResponse,
    dependencies=[Depends(verify_internal_api_key)],
)
async def disconnect_installation(
    payload: TeamsInstallationDisconnect, service: InstallationServiceDep
) -> dict:
    return await service.disconnect(payload)


@router.get(
    "/integrations",
    response_model=list[TeamsIntegrationOverviewItem],
    dependencies=[Depends(verify_internal_api_key)],
)
async def list_integrations(service: InstallationServiceDep) -> list[dict]:
    return await service.integrations_overview()


@router.get(
    "/integration/{accountId}",
    response_model=TeamsIntegrationStatus,
)
async def get_integration_status(
    accountId: str, service: InstallationServiceDep
) -> dict:
    return await service.integration_status(accountId)


@router.get(
    "/installations/{accountId}",
    response_model=list[TeamsInstallationResponse],
    dependencies=[Depends(verify_internal_api_key)],
)
async def list_installations(
    accountId: str, service: InstallationServiceDep
) -> list[dict]:
    return [serialize_installation(item) for item in await service.list_by_account(accountId)]


@router.get(
    "/installation-summaries/{accountId}",
    response_model=list[TeamsInstallationSummary],
    summary="List browser-safe Teams destinations for an account",
)
async def list_installation_summaries(
    accountId: str, service: InstallationServiceDep
) -> list[dict]:
    # accountId is the existing MVP selected-account context, not production auth.
    return await service.list_summaries_by_account(accountId)


@router.patch(
    "/installations/{accountId}/{installationId}/route",
    response_model=TeamsInstallationResponse,
    dependencies=[Depends(verify_internal_api_key)],
)
async def assign_installation_route(
    accountId: str,
    installationId: str,
    payload: TeamsInstallationRouteUpdate,
    service: InstallationServiceDep,
) -> dict:
    return serialize_installation(
        await service.assign_route(accountId, installationId, payload.routeKey)
    )


@router.post(
    "/channel-destinations",
    response_model=TeamsChannelDestinationRegistrationResponse,
    dependencies=[Depends(verify_internal_api_key)],
)
async def register_channel_destination(
    payload: TeamsChannelDestinationCreate,
    service: ChannelDestinationServiceDep,
) -> dict:
    destination = await service.register(payload)
    return {
        "success": True,
        "destination": serialize_channel_destination(destination),
    }


@router.get(
    "/channel-destinations/{accountId}",
    response_model=list[TeamsChannelDestinationSummary],
)
async def list_channel_destinations(
    accountId: str, service: ChannelDestinationServiceDep
) -> list[dict]:
    # Existing selected-account MVP context; production authorization is separate.
    return await service.list_safe_by_account(accountId)


@router.get(
    "/channel-destinations-internal/{accountId}",
    response_model=list[TeamsChannelDestinationResponse],
    dependencies=[Depends(verify_internal_api_key)],
)
async def list_channel_destinations_internal(
    accountId: str, service: ChannelDestinationServiceDep
) -> list[dict]:
    return [
        serialize_channel_destination(item)
        for item in await service.list_by_account(accountId)
    ]


@router.put(
    "/destinations/{accountId}",
    response_model=TeamDestinationResponse,
    status_code=status.HTTP_200_OK,
    summary="Create or update a Teams destination",
    description="Upserts the Teams team/channel mapping for a given accountId.",
)
async def upsert_destination(
    accountId: str, payload: TeamDestinationCreate, service: DestinationServiceDep
) -> dict:
    result = await service.upsert_destination(accountId, payload)
    return strip_mongo_id(result)


@router.get(
    "/destinations/{accountId}",
    response_model=TeamDestinationResponse,
    summary="Get a Teams destination",
    description="Fetch the Teams team/channel mapping for a given accountId.",
)
async def get_destination(accountId: str, service: DestinationServiceDep) -> dict:
    result = await service.get_destination(accountId)
    return strip_mongo_id(result)


@router.get(
    "/destinations",
    response_model=list[TeamDestinationResponse],
    summary="List Teams destinations",
    description="List all configured Teams destination mappings.",
)
async def list_destinations(service: DestinationServiceDep) -> list[dict]:
    results = await service.list_destinations()
    return strip_mongo_id_list(results)
