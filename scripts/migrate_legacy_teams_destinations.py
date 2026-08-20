"""Migrate recoverable legacy Teams routes into channel destinations.

Usage:
    python -m scripts.migrate_legacy_teams_destinations --dry-run
    python -m scripts.migrate_legacy_teams_destinations --apply

The migration never deletes or edits source documents. Existing channel
destinations win over legacy data, making repeated runs safe.
"""
import argparse
import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import get_settings


REQUIRED_FIELDS = (
    "accountId", "tenantId", "teamId", "channelId", "conversationId", "serviceUrl"
)


async def migrate_legacy_teams_destinations(
    db: AsyncIOMotorDatabase, *, apply: bool
) -> dict[str, int]:
    summary = {"scanned": 0, "recoverable": 0, "inserted": 0, "existing": 0,
               "quarantined": 0}
    mappings = {
        item["accountId"]: item
        async for item in db.tenant_mappings.find({"accountId": {"$type": "string"}})
    }

    async def process(source: str, document: dict[str, Any]) -> None:
        summary["scanned"] += 1
        fields = {key: document.get(key) for key in (
            *REQUIRED_FIELDS, "teamName", "channelName", "connectedByName"
        )}
        mapping = mappings.get(fields["accountId"])
        fields["tenantId"] = fields.get("tenantId") or (
            mapping.get("tenantId") if mapping else None
        )
        if (
            fields.get("conversationId") == fields.get("teamId")
            and fields.get("channelId") != fields.get("teamId")
        ):
            fields["conversationId"] = fields.get("channelId")

        missing = [field for field in REQUIRED_FIELDS if not fields.get(field)]
        if missing:
            summary["quarantined"] += 1
            print(json.dumps({
                "mode": "apply" if apply else "dry-run", "status": "quarantined",
                "source": source, "sourceId": str(document.get("_id")),
                "accountId": fields.get("accountId"), "missing": missing,
            }))
            return

        summary["recoverable"] += 1
        key = {field: fields[field] for field in (
            "accountId", "tenantId", "teamId", "channelId"
        )}
        existing = await db.teams_channel_destinations.find_one(key, {"_id": 1})
        if existing:
            summary["existing"] += 1
            status = "existing"
        else:
            status = "would_insert"
            if apply:
                now = datetime.now(timezone.utc)
                destination = {key: value for key, value in fields.items() if value is not None}
                destination.update({
                    "enabled": document.get("enabled", True) is True,
                    "createdAt": document.get("createdAt", now),
                    "updatedAt": document.get("updatedAt", now),
                    "connectedAt": document.get("connectedAt", document.get("createdAt", now)),
                    "disconnectedAt": document.get("disconnectedAt"),
                    "disconnectReason": document.get("disconnectReason"),
                    "disconnectSource": document.get("disconnectSource"),
                })
                result = await db.teams_channel_destinations.update_one(
                    key, {"$setOnInsert": destination}, upsert=True
                )
                if result.upserted_id is None:
                    summary["existing"] += 1
                    status = "existing"
                else:
                    summary["inserted"] += 1
                    status = "inserted"
        print(json.dumps({
            "mode": "apply" if apply else "dry-run", "status": status,
            "source": source, **key,
        }))

    async for document in db.teams_destinations.find({}):
        await process("teams_destinations", document)
    async for document in db.teams_installations.find({
        "channelId": {"$type": "string"}
    }):
        await process("teams_installations", document)

    print(json.dumps({"mode": "apply" if apply else "dry-run", **summary}))
    return summary


async def main(apply: bool) -> None:
    settings = get_settings()
    client = AsyncIOMotorClient(settings.mongodb_url)
    try:
        await migrate_legacy_teams_destinations(
            client[settings.mongodb_db_name], apply=apply
        )
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(apply=args.apply))
