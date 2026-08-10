"""Business logic for Teams destination mappings (accountId -> team/channel)."""
from typing import Any

from app.exceptions.handlers import TeamsDestinationNotFoundError
from app.repositories.teams_destination_repository import TeamsDestinationRepository
from app.schemas.teams import TeamDestinationCreate


class TeamsDestinationService:
    def __init__(self, repository: TeamsDestinationRepository):
        self._repo = repository

    async def upsert_destination(
        self, account_id: str, payload: TeamDestinationCreate
    ) -> dict[str, Any]:
        return await self._repo.upsert(account_id, payload.model_dump(mode="json"))

    async def get_destination(self, account_id: str) -> dict[str, Any]:
        destination = await self._repo.get_by_account_id(account_id)
        if not destination:
            raise TeamsDestinationNotFoundError()
        return destination

    async def list_destinations(self) -> list[dict[str, Any]]:
        return await self._repo.list()
