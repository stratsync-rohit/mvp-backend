"""Business logic for reading notification logs."""
from typing import Any, Optional

from app.exceptions.handlers import NotificationLogNotFoundError
from app.repositories.notification_log_repository import NotificationLogRepository


class NotificationLogService:
    def __init__(self, repository: NotificationLogRepository):
        self._repo = repository

    async def list_logs(
        self,
        risk_id: Optional[str] = None,
        status: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> list[dict[str, Any]]:
        return await self._repo.list(
            risk_id=risk_id, status=status, event_type=event_type, limit=limit, skip=skip
        )

    async def get_log(self, event_id: str) -> dict[str, Any]:
        log = await self._repo.get_by_event_id(event_id)
        if not log:
            raise NotificationLogNotFoundError()
        return log
