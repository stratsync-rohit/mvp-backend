"""Repair channel destinations polluted with a Team-level conversation ID.

Usage:
    python -m scripts.repair_teams_channel_conversations --dry-run
    python -m scripts.repair_teams_channel_conversations --apply
"""
import argparse
import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import get_settings


async def repair_teams_channel_conversations(
    db: AsyncIOMotorDatabase, *, apply: bool
) -> list[dict[str, Any]]:
    repaired: list[dict[str, Any]] = []
    cursor = db.teams_channel_destinations.find({
        "enabled": True,
        "teamId": {"$type": "string"},
        "channelId": {"$type": "string"},
        "conversationId": {"$type": "string"},
    })
    async for destination in cursor:
        team_id = destination["teamId"]
        channel_id = destination["channelId"]
        if destination["conversationId"] != team_id or channel_id == team_id:
            continue
        if destination.get("conversationType") in {"personal", "groupChat", "meeting"}:
            continue

        update: dict[str, Any] = {"conversationId": channel_id}
        if not destination.get("teamName"):
            installation = await db.teams_installations.find_one({
                "accountId": destination.get("accountId"),
                "tenantId": destination.get("tenantId"),
                "teamId": team_id,
                "enabled": True,
                "teamName": {"$type": "string"},
            })
            if installation and installation.get("teamName"):
                update["teamName"] = installation["teamName"]

        item = {
            "destinationId": str(destination["_id"]),
            "accountId": destination.get("accountId"),
            "teamId": team_id,
            "channelId": channel_id,
            "teamNameEnriched": "teamName" in update,
        }
        repaired.append(item)
        print(json.dumps({"mode": "apply" if apply else "dry-run", **item}))
        if apply:
            update["updatedAt"] = datetime.now(timezone.utc)
            await db.teams_channel_destinations.update_one(
                {
                    "_id": destination["_id"],
                    "enabled": True,
                    "conversationId": team_id,
                    "channelId": channel_id,
                },
                {"$set": update},
            )
    return repaired


async def main(apply: bool) -> None:
    settings = get_settings()
    client = AsyncIOMotorClient(settings.mongodb_url)
    try:
        db = client[settings.mongodb_db_name]
        repaired = await repair_teams_channel_conversations(db, apply=apply)
        print(json.dumps({"mode": "apply" if apply else "dry-run", "matched": len(repaired)}))
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(apply=args.apply))
