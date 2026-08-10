"""Teams destination mapping endpoints (accountId -> team/channel)."""
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.dependencies import get_teams_destination_service
from app.schemas.teams import TeamDestinationCreate, TeamDestinationResponse
from app.services.teams_destination_service import TeamsDestinationService
from app.utils.serializers import strip_mongo_id, strip_mongo_id_list

router = APIRouter(prefix="/api/teams", tags=["Teams Destinations"])

DestinationServiceDep = Annotated[TeamsDestinationService, Depends(get_teams_destination_service)]


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
