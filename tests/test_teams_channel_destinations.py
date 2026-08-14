import pytest

from app.database import mongo_manager
from app.services.n8n_service import N8nService


async def map_tenant(async_client, account_id, tenant_id):
    await async_client.put(f"/api/teams/tenant-mappings/{account_id}", json={
        "tenantId": tenant_id, "clientName": account_id, "enabled": True,
    })


def destination(tenant_id, channel_id, channel_name):
    return {
        "tenantId": tenant_id,
        "teamId": f"team-{tenant_id}",
        "teamName": "Stratsync.ai",
        "channelId": channel_id,
        "channelName": channel_name,
        "conversationId": f"conversation-{channel_id}",
        "serviceUrl": "https://example.test/",
        "connectedByName": "Installer",
    }


@pytest.mark.asyncio
async def test_same_team_channels_upsert_independently_and_reactivate(async_client):
    await map_tenant(async_client, "ACC-001", "TENANT-A")
    sales = await async_client.post(
        "/api/teams/channel-destinations",
        json=destination("TENANT-A", "SALES-ID", "Sales"),
    )
    dev = await async_client.post(
        "/api/teams/channel-destinations",
        json=destination("TENANT-A", "DEV-ID", "Dev"),
    )
    assert sales.status_code == dev.status_code == 200
    assert sales.json()["destination"]["destinationId"] != dev.json()["destination"]["destinationId"]
    assert await mongo_manager.database.teams_channel_destinations.count_documents({
        "accountId": "ACC-001"
    }) == 2

    repeated = await async_client.post(
        "/api/teams/channel-destinations",
        json={**destination("TENANT-A", "SALES-ID", "Sales Alerts")},
    )
    assert repeated.json()["destination"]["destinationId"] == sales.json()["destination"]["destinationId"]
    assert repeated.json()["destination"]["channelName"] == "Sales Alerts"
    assert await mongo_manager.database.teams_channel_destinations.count_documents({
        "accountId": "ACC-001"
    }) == 2

    await mongo_manager.database.teams_channel_destinations.update_one(
        {"channelId": "SALES-ID"},
        {"$set": {"enabled": False, "disconnectedAt": "old"}},
    )
    reactivated = await async_client.post(
        "/api/teams/channel-destinations",
        json=destination("TENANT-A", "SALES-ID", "Sales"),
    )
    assert reactivated.json()["destination"]["enabled"] is True
    assert reactivated.json()["destination"]["disconnectedAt"] is None


@pytest.mark.asyncio
async def test_safe_lists_are_account_scoped_and_hide_routing_fields(async_client):
    await map_tenant(async_client, "ACC-001", "TENANT-A")
    await map_tenant(async_client, "ACC-002", "TENANT-B")
    await async_client.post(
        "/api/teams/channel-destinations",
        json=destination("TENANT-A", "SALES-ID", "Sales"),
    )
    await async_client.post(
        "/api/teams/channel-destinations",
        json=destination("TENANT-B", "FINANCE-ID", "Finance"),
    )
    account_a = (await async_client.get(
        "/api/teams/channel-destinations/ACC-001"
    )).json()
    account_b = (await async_client.get(
        "/api/teams/channel-destinations/ACC-002"
    )).json()
    assert [item["channelName"] for item in account_a] == ["Sales"]
    assert [item["channelName"] for item in account_b] == ["Finance"]
    assert set(account_a[0]) == {"destinationId", "teamName", "channelName", "connected"}


@pytest.mark.asyncio
async def test_destination_send_is_exact_isolated_and_rejects_disabled(
    async_client, sample_risk_payload, monkeypatch
):
    captured = []

    async def trigger(self, url, payload, event_id):
        captured.append(payload)
        return {"status": "received"}

    monkeypatch.setattr(N8nService, "trigger_webhook", trigger)
    await map_tenant(async_client, "ACC-001", "TENANT-A")
    await map_tenant(async_client, "ACC-002", "TENANT-B")
    await async_client.post("/api/risks", json=sample_risk_payload)
    sales = (await async_client.post(
        "/api/teams/channel-destinations",
        json=destination("TENANT-A", "SALES-ID", "Sales"),
    )).json()["destination"]
    finance = (await async_client.post(
        "/api/teams/channel-destinations",
        json=destination("TENANT-B", "FINANCE-ID", "Finance"),
    )).json()["destination"]

    sent = await async_client.post(
        "/api/risks/RSK-OP-0821/send-to-teams",
        json={"destinationId": sales["destinationId"]},
    )
    assert sent.status_code == 200
    assert captured[-1]["teamsDestination"]["channelId"] == "SALES-ID"

    cross = await async_client.post(
        "/api/risks/RSK-OP-0821/send-to-teams",
        json={"destinationId": finance["destinationId"]},
    )
    assert cross.status_code == 404
    await mongo_manager.database.teams_channel_destinations.update_one(
        {"channelId": "SALES-ID"}, {"$set": {"enabled": False}},
    )
    disabled = await async_client.post(
        "/api/risks/RSK-OP-0821/send-to-teams",
        json={"destinationId": sales["destinationId"]},
    )
    assert disabled.status_code == 409
    assert disabled.json()["detail"] == "Microsoft Teams destination is no longer connected."
    assert len(captured) == 1


@pytest.mark.asyncio
async def test_team_uninstall_disables_only_that_teams_destinations(async_client):
    await map_tenant(async_client, "ACC-001", "TENANT-A")
    await async_client.post("/api/teams/installations", json={
        "tenantId": "TENANT-A", "teamId": "team-TENANT-A",
        "channelId": "SALES-ID", "conversationId": "installation-conversation",
        "serviceUrl": "https://example.test/", "botAppId": "bot",
    })
    for channel_id, name in (("SALES-ID", "Sales"), ("DEV-ID", "Dev")):
        await async_client.post(
            "/api/teams/channel-destinations",
            json=destination("TENANT-A", channel_id, name),
        )
    removed = await async_client.post(
        "/api/teams/installations/disconnect",
        json={
            "tenantId": "TENANT-A",
            "teamId": "team-TENANT-A",
            "conversationId": "different-team-lifecycle-conversation",
        },
    )
    assert removed.status_code == 200
    assert await mongo_manager.database.teams_channel_destinations.count_documents({
        "accountId": "ACC-001", "enabled": False,
    }) == 2
