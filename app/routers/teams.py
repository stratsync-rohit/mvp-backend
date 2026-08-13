"""Teams destination mapping endpoints (accountId -> team/channel)."""
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.dependencies import (
    get_teams_destination_service,
    get_teams_installation_service,
    get_tenant_mapping_service,
    verify_internal_api_key,
)
from app.schemas.teams import (
    TeamDestinationCreate,
    TeamDestinationResponse,
    TeamsInstallationCreate,
    TeamsInstallationDisconnect,
    TeamsInstallationDisconnectResponse,
    TeamsInstallationRegistrationResponse,
    TeamsInstallationResponse,
    TeamsIntegrationOverviewItem,
    TeamsIntegrationStatus,
    TenantMappingCreate,
    TenantMappingResponse,
    TenantMappingUpsertResponse,
)
from app.services.teams_destination_service import TeamsDestinationService
from app.services.teams_installation_service import TeamsInstallationService
from app.services.tenant_mapping_service import TenantMappingService
from app.utils.serializers import strip_mongo_id, strip_mongo_id_list

router = APIRouter(prefix="/api/teams", tags=["Teams Destinations"])

DestinationServiceDep = Annotated[TeamsDestinationService, Depends(get_teams_destination_service)]
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
        "installation": strip_mongo_id(installation),
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
    "/installations/{accountId}", response_model=list[TeamsInstallationResponse]
)
async def list_installations(
    accountId: str, service: InstallationServiceDep
) -> list[dict]:
    return strip_mongo_id_list(await service.list_by_account(accountId))


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
