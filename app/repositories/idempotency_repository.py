"""
Minimal idempotency support.

Stores a mapping of `Idempotency-Key` -> the last successful response body,
scoped per-endpoint via a `scope` field so the same key can't accidentally
collide across different operations.
"""
from datetime import datetime, timezone
from typing import Any, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase


class IdempotencyRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._collection = db.idempotency_keys

    async def get(self, key: str, scope: str) -> Optional[dict[str, Any]]:
        return await self._collection.find_one({"key": key, "scope": scope})

    async def save_result(self, key: str, scope: str, result: dict[str, Any]) -> None:
        # Use update_one with upsert so a retry racing with itself doesn't
        # error out on the unique index; last write wins for this basic
        # implementation which is acceptable for the current testing scope.
        await self._collection.update_one(
            {"key": key, "scope": scope},
            {
                "$set": {
                    "key": key,
                    "scope": scope,
                    "result": result,
                    "createdAt": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )
