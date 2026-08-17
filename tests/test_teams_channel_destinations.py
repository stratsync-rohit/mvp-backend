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
    assert set(account_a[0]) == {
        "destinationId", "teamName", "channelName", "connected",
        "disconnectReason", "disconnectedAt",
    }


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
    dev = (await async_client.post(
        "/api/teams/channel-destinations",
        json=destination("TENANT-A", "DEV-ID", "Dev"),
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

    sent_to_dev = await async_client.post(
        "/api/risks/RSK-OP-0821/send-to-teams",
        json={"destinationId": dev["destinationId"]},
    )
    assert sent_to_dev.status_code == 200
    assert captured[-1]["teamsDestination"]["channelId"] == "DEV-ID"

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
    assert len(captured) == 2


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


@pytest.mark.asyncio
async def test_manual_remove_is_scoped_soft_idempotent_and_reactivates(async_client):
    await map_tenant(async_client, "ACC-001", "TENANT-A")
    await map_tenant(async_client, "ACC-002", "TENANT-B")
    first = (await async_client.post(
        "/api/teams/channel-destinations",
        json=destination("TENANT-A", "SALES-ID", "Sales"),
    )).json()["destination"]
    sibling = (await async_client.post(
        "/api/teams/channel-destinations",
        json=destination("TENANT-A", "DEV-ID", "Dev"),
    )).json()["destination"]

    cross_account = await async_client.delete(
        f"/api/teams/channel-destinations/ACC-002/{first['destinationId']}"
    )
    assert cross_account.status_code == 404

    removed = await async_client.delete(
        f"/api/teams/channel-destinations/ACC-001/{first['destinationId']}"
    )
    assert removed.status_code == 200
    assert removed.json() == {
        "success": True, "destinationId": first["destinationId"],
        "connected": False, "message": "Teams channel removed successfully",
    }
    document = await mongo_manager.database.teams_channel_destinations.find_one(
        {"_id": __import__("bson").ObjectId(first["destinationId"])}
    )
    assert document["enabled"] is False
    assert document["disconnectReason"] == "manual_removal"
    assert document["disconnectSource"] == "stratsync_ui"
    assert document["disconnectedAt"] is not None
    assert await mongo_manager.database.teams_channel_destinations.count_documents({}) == 2
    assert (await mongo_manager.database.teams_channel_destinations.find_one(
        {"_id": __import__("bson").ObjectId(sibling["destinationId"])}
    ))["enabled"] is True

    repeated = await async_client.delete(
        f"/api/teams/channel-destinations/ACC-001/{first['destinationId']}"
    )
    assert repeated.status_code == 200
    assert (await async_client.delete(
        "/api/teams/channel-destinations/ACC-001/not-an-object-id"
    )).status_code == 404

    safe = (await async_client.get(
        "/api/teams/channel-destinations/ACC-001"
    )).json()
    removed_safe = next(item for item in safe if item["destinationId"] == first["destinationId"])
    assert removed_safe["disconnectReason"] == "manual_removal"
    assert "serviceUrl" not in removed_safe and "conversationId" not in removed_safe

    reactivated = (await async_client.post(
        "/api/teams/channel-destinations",
        json=destination("TENANT-A", "SALES-ID", "Sales restored"),
    )).json()["destination"]
    assert reactivated["destinationId"] == first["destinationId"]
    assert reactivated["enabled"] is True
    assert reactivated["disconnectedAt"] is None
    stored = await mongo_manager.database.teams_channel_destinations.find_one(
        {"_id": __import__("bson").ObjectId(first["destinationId"])}
    )
    assert stored["disconnectReason"] is None
    assert await mongo_manager.database.teams_channel_destinations.count_documents({}) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("result", "disabled", "reason", "code"),
    [
        ({"success": False, "errorCode": "conversation_not_found", "retryable": False}, True, "channel_deleted", "conversation_not_found"),
        ({"success": False, "errorCode": "microsoft_server_error", "retryable": True}, False, None, "microsoft_server_error"),
        ({"success": False, "errorCode": "unknown_error", "retryable": True}, False, None, "unknown_error"),
    ],
)
async def test_delivery_result_disconnects_only_definitive_failures(
    async_client, sample_risk_payload, monkeypatch, result, disabled, reason, code
):
    async def trigger(self, url, payload, event_id):
        assert payload["teamsDestination"]["destinationId"] == selected["destinationId"]
        return result

    monkeypatch.setattr(N8nService, "trigger_webhook", trigger)
    await map_tenant(async_client, "ACC-001", "TENANT-A")
    await async_client.post("/api/risks", json=sample_risk_payload)
    selected = (await async_client.post(
        "/api/teams/channel-destinations",
        json=destination("TENANT-A", "SALES-ID", "Sales"),
    )).json()["destination"]

    response = await async_client.post(
        "/api/risks/RSK-OP-0821/send-to-teams",
        json={"destinationId": selected["destinationId"]},
    )
    assert response.status_code == 502
    stored = await mongo_manager.database.teams_channel_destinations.find_one(
        {"_id": __import__("bson").ObjectId(selected["destinationId"])}
    )
    assert stored["enabled"] is (not disabled)
    assert stored.get("disconnectReason") == reason
    assert stored["lastDeliveryErrorCode"] == code
    assert stored["consecutiveDeliveryFailures"] == 1
