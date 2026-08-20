import pytest

from app.database import mongo_manager
from scripts.migrate_legacy_teams_destinations import migrate_legacy_teams_destinations


@pytest.mark.asyncio
async def test_legacy_destination_migration_is_dry_run_idempotent_and_quarantines():
    db = mongo_manager.database
    await db.tenant_mappings.insert_one({
        "accountId": "ACC-001", "tenantId": "TENANT-A", "enabled": True,
    })
    await db.teams_destinations.insert_one({
        "accountId": "ACC-001", "teamId": "TEAM-A", "channelId": "CHANNEL-A",
        "conversationId": "CONVERSATION-A", "serviceUrl": "https://legacy.test/",
        "teamName": "Team A", "channelName": "Channel A", "enabled": True,
    })
    await db.teams_installations.insert_one({
        "accountId": "ACC-001", "tenantId": "TENANT-A", "teamId": "TEAM-B",
        "channelId": "CHANNEL-B", "conversationId": "CONVERSATION-B",
        "serviceUrl": "https://installation.test/", "enabled": False,
    })
    await db.teams_installations.insert_one({
        "accountId": "ACC-001", "tenantId": "TENANT-A", "teamId": "TEAM-C",
        "channelId": "CHANNEL-C", "conversationId": "CONVERSATION-C",
    })

    dry_run = await migrate_legacy_teams_destinations(db, apply=False)
    assert dry_run == {
        "scanned": 3, "recoverable": 2, "inserted": 0,
        "existing": 0, "quarantined": 1,
    }
    assert await db.teams_channel_destinations.count_documents({}) == 0

    applied = await migrate_legacy_teams_destinations(db, apply=True)
    assert applied["inserted"] == 2
    assert await db.teams_channel_destinations.count_documents({}) == 2
    migrated_a = await db.teams_channel_destinations.find_one({"channelId": "CHANNEL-A"})
    migrated_b = await db.teams_channel_destinations.find_one({"channelId": "CHANNEL-B"})
    assert migrated_a["tenantId"] == "TENANT-A"
    assert migrated_a["serviceUrl"] == "https://legacy.test/"
    assert migrated_b["enabled"] is False

    repeated = await migrate_legacy_teams_destinations(db, apply=True)
    assert repeated["inserted"] == 0
    assert repeated["existing"] == 2
    assert await db.teams_channel_destinations.count_documents({}) == 2
