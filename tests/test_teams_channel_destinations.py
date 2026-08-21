import pytest

from app.database import mongo_manager
from app.services.n8n_service import N8nService
from scripts.repair_teams_channel_conversations import repair_teams_channel_conversations


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
        "conversationId": channel_id,
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
async def test_three_channels_same_team_and_two_teams_same_tenant_coexist(async_client):
    await map_tenant(async_client, "ACC-001", "TENANT-A")
    created = []
    for team_id, channel_id in (
        ("TEAM-STRATSYNC", "FINAL-TEST"),
        ("TEAM-STRATSYNC", "FINAL2"),
        ("TEAM-STRATSYNC", "R2"),
        ("TEAM-ROHIT-TEST", "TEST"),
    ):
        payload = destination("TENANT-A", channel_id, channel_id)
        payload["teamId"] = team_id
        response = await async_client.post("/api/teams/channel-destinations", json=payload)
        assert response.status_code == 200
        created.append(response.json()["destination"])

    assert len({item["destinationId"] for item in created}) == 4
    assert await mongo_manager.database.teams_channel_destinations.count_documents({
        "accountId": "ACC-001", "tenantId": "TENANT-A", "enabled": True,
    }) == 4


@pytest.mark.asyncio
async def test_two_teams_four_channels_uninstall_reinstall_and_route_independently(
    async_client, sample_risk_payload, monkeypatch
):
    captured = []

    async def trigger(self, url, payload, event_id):
        captured.append(payload)
        return {"success": True}

    monkeypatch.setattr(N8nService, "trigger_webhook", trigger)
    await map_tenant(async_client, "ACC-001", "TENANT-A")
    await async_client.post("/api/risks", json=sample_risk_payload)

    installations = {}
    for team_id, team_name in (
        ("TEAM-SALES", "Sales Org"),
        ("TEAM-ENGINEERING", "Engineering"),
    ):
        response = await async_client.post("/api/teams/installations", json={
            "tenantId": "TENANT-A", "teamId": team_id,
            "conversationId": team_id, "serviceUrl": "https://example.test/",
            "teamName": team_name, "botAppId": "bot",
        })
        assert response.status_code == 200
        installations[team_id] = response.json()["installation"]["installationId"]

    assert len(set(installations.values())) == 2
    assert await mongo_manager.database.teams_installations.count_documents({
        "accountId": "ACC-001", "tenantId": "TENANT-A",
    }) == 2

    channel_specs = (
        ("TEAM-SALES", "Sales Org", "CHANNEL-SALES-ALERTS", "Alerts"),
        ("TEAM-SALES", "Sales Org", "CHANNEL-LEADERSHIP", "Leadership"),
        ("TEAM-ENGINEERING", "Engineering", "CHANNEL-DEV", "Alerts"),
        ("TEAM-ENGINEERING", "Engineering", "CHANNEL-INCIDENTS", "Incidents"),
    )
    created = {}
    for team_id, team_name, channel_id, channel_name in channel_specs:
        payload = destination("TENANT-A", channel_id, channel_name)
        payload.update({"teamId": team_id, "teamName": team_name})
        response = await async_client.post("/api/teams/channel-destinations", json=payload)
        assert response.status_code == 200
        created[channel_id] = response.json()["destination"]

    assert len({item["destinationId"] for item in created.values()}) == 4
    assert await mongo_manager.database.teams_channel_destinations.count_documents({
        "accountId": "ACC-001", "tenantId": "TENANT-A",
    }) == 4
    assert await mongo_manager.database.teams_channel_destinations.count_documents({
        "accountId": "ACC-001", "channelName": "Alerts",
    }) == 2

    listed = (await async_client.get(
        "/api/teams/channel-destinations/ACC-001"
    )).json()
    assert {(item["teamName"], item["channelName"]) for item in listed} == {
        ("Sales Org", "Alerts"), ("Sales Org", "Leadership"),
        ("Engineering", "Alerts"), ("Engineering", "Incidents"),
    }

    removed = await async_client.post("/api/teams/installations/disconnect", json={
        "tenantId": "TENANT-A", "teamId": "TEAM-SALES", "scope": "team",
    })
    assert removed.status_code == 200
    assert await mongo_manager.database.teams_installations.count_documents({
        "accountId": "ACC-001", "teamId": "TEAM-SALES", "enabled": False,
    }) == 1
    assert await mongo_manager.database.teams_installations.count_documents({
        "accountId": "ACC-001", "teamId": "TEAM-ENGINEERING", "enabled": True,
    }) == 1
    assert await mongo_manager.database.teams_channel_destinations.count_documents({
        "accountId": "ACC-001", "teamId": "TEAM-SALES", "enabled": False,
    }) == 2
    assert await mongo_manager.database.teams_channel_destinations.count_documents({
        "accountId": "ACC-001", "teamId": "TEAM-ENGINEERING", "enabled": True,
    }) == 2

    await async_client.post("/api/teams/installations", json={
        "tenantId": "TENANT-A", "teamId": "TEAM-SALES",
        "conversationId": "TEAM-SALES", "serviceUrl": "https://example.test/",
        "teamName": "Sales Org", "botAppId": "bot",
    })
    assert await mongo_manager.database.teams_channel_destinations.count_documents({
        "accountId": "ACC-001", "teamId": "TEAM-SALES", "enabled": False,
    }) == 2
    assert await mongo_manager.database.teams_channel_destinations.count_documents({
        "accountId": "ACC-001", "teamId": "TEAM-ENGINEERING", "enabled": True,
    }) == 2

    sales_alerts_payload = destination("TENANT-A", "CHANNEL-SALES-ALERTS", "Alerts")
    sales_alerts_payload.update({"teamId": "TEAM-SALES", "teamName": "Sales Org"})
    restored = (await async_client.post(
        "/api/teams/channel-destinations", json=sales_alerts_payload
    )).json()["destination"]
    assert restored["destinationId"] == created["CHANNEL-SALES-ALERTS"]["destinationId"]

    for channel_id in ("CHANNEL-SALES-ALERTS", "CHANNEL-DEV"):
        response = await async_client.post(
            "/api/risks/RSK-OP-0821/send-to-teams",
            json={"destinationId": created[channel_id]["destinationId"]},
        )
        assert response.status_code == 200

    assert [(item["teamsDestination"]["teamId"],
             item["teamsDestination"]["channelId"]) for item in captured] == [
        ("TEAM-SALES", "CHANNEL-SALES-ALERTS"),
        ("TEAM-ENGINEERING", "CHANNEL-DEV"),
    ]


@pytest.mark.asyncio
async def test_updating_one_channel_preserves_sibling_routing_and_state(async_client):
    await map_tenant(async_client, "ACC-001", "TENANT-A")
    first = (await async_client.post(
        "/api/teams/channel-destinations",
        json=destination("TENANT-A", "CHANNEL-A", "Channel A"),
    )).json()["destination"]
    await async_client.post(
        "/api/teams/channel-destinations",
        json=destination("TENANT-A", "CHANNEL-B", "Channel B"),
    )
    before = await mongo_manager.database.teams_channel_destinations.find_one(
        {"_id": __import__("bson").ObjectId(first["destinationId"])}
    )

    await async_client.post(
        "/api/teams/channel-destinations",
        json={**destination("TENANT-A", "CHANNEL-B", "Renamed B"),
              "conversationId": "conversation-b-new"},
    )
    after = await mongo_manager.database.teams_channel_destinations.find_one(
        {"_id": before["_id"]}
    )
    protected = (
        "_id", "accountId", "tenantId", "teamId", "channelId",
        "conversationId", "serviceUrl", "enabled", "connectedAt",
        "disconnectedAt", "disconnectReason", "disconnectSource", "updatedAt",
    )
    assert {field: before.get(field) for field in protected} == {
        field: after.get(field) for field in protected
    }


@pytest.mark.asyncio
async def test_channel_scoped_disconnect_does_not_disable_sibling(async_client):
    await map_tenant(async_client, "ACC-001", "TENANT-A")
    for channel_id in ("CHANNEL-A", "CHANNEL-B"):
        await async_client.post(
            "/api/teams/channel-destinations",
            json=destination("TENANT-A", channel_id, channel_id),
        )
    removed = await async_client.post(
        "/api/teams/installations/disconnect",
        json={"tenantId": "TENANT-A", "teamId": "team-TENANT-A",
              "channelId": "CHANNEL-A", "scope": "channel"},
    )
    assert removed.status_code == 200
    assert removed.json()["disconnected"] is True
    channel_a = await mongo_manager.database.teams_channel_destinations.find_one(
        {"channelId": "CHANNEL-A"}
    )
    channel_b = await mongo_manager.database.teams_channel_destinations.find_one(
        {"channelId": "CHANNEL-B"}
    )
    assert channel_a["enabled"] is False
    assert channel_a["disconnectReason"] == "channel_removed"
    assert channel_b["enabled"] is True


@pytest.mark.asyncio
async def test_multiple_channels_require_destination_id_but_single_channel_falls_back(
    async_client, sample_risk_payload, monkeypatch
):
    captured = []

    async def trigger(self, url, payload, event_id):
        captured.append(payload)
        return {"success": True}

    monkeypatch.setattr(N8nService, "trigger_webhook", trigger)
    await map_tenant(async_client, "ACC-001", "TENANT-A")
    await async_client.post("/api/risks", json=sample_risk_payload)
    await async_client.post(
        "/api/teams/channel-destinations",
        json=destination("TENANT-A", "CHANNEL-A", "Channel A"),
    )
    single = await async_client.post("/api/risks/RSK-OP-0821/send-to-teams")
    assert single.status_code == 200
    assert captured[-1]["teamsDestination"]["channelId"] == "CHANNEL-A"

    await async_client.post(
        "/api/teams/channel-destinations",
        json=destination("TENANT-A", "CHANNEL-B", "Channel B"),
    )
    ambiguous = await async_client.post("/api/risks/RSK-OP-0821/send-to-teams")
    assert ambiguous.status_code == 409
    assert ambiguous.json()["detail"] == (
        "Multiple Microsoft Teams channels are connected. destinationId is required."
    )
    assert len(captured) == 1


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
    await async_client.post("/api/teams/installations", json={
        "tenantId": "TENANT-A", "teamId": "OTHER-TEAM",
        "channelId": "OTHER-ID", "conversationId": "other-conversation",
        "serviceUrl": "https://example.test/", "botAppId": "bot",
    })
    await async_client.post(
        "/api/teams/channel-destinations",
        json={**destination("TENANT-A", "OTHER-ID", "Other"),
              "teamId": "OTHER-TEAM"},
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
        "accountId": "ACC-001", "teamId": "team-TENANT-A", "enabled": False,
    }) == 2
    assert await mongo_manager.database.teams_channel_destinations.count_documents({
        "accountId": "ACC-001", "teamId": "OTHER-TEAM", "enabled": True,
    }) == 1


@pytest.mark.asyncio
async def test_manual_disconnect_and_reconnect_preserve_exact_destination(
    async_client,
):
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
    other_team_payload = destination("TENANT-A", "OPS-ID", "Operations")
    other_team_payload["teamId"] = "OTHER-TEAM"
    other_team = (await async_client.post(
        "/api/teams/channel-destinations", json=other_team_payload,
    )).json()["destination"]
    other_account = (await async_client.post(
        "/api/teams/channel-destinations",
        json=destination("TENANT-B", "FINANCE-ID", "Finance"),
    )).json()["destination"]

    cross_account = await async_client.post(
        f"/api/teams/channel-destinations/ACC-002/{first['destinationId']}/disconnect"
    )
    assert cross_account.status_code == 404

    removed = await async_client.post(
        f"/api/teams/channel-destinations/ACC-001/{first['destinationId']}/disconnect"
    )
    assert removed.status_code == 200
    assert removed.json()["destinationId"] == first["destinationId"]
    document = await mongo_manager.database.teams_channel_destinations.find_one(
        {"_id": __import__("bson").ObjectId(first["destinationId"])}
    )
    assert document["enabled"] is False
    assert document["disconnectReason"] == "manual_disconnect"
    assert document["disconnectedAt"] is not None
    assert await mongo_manager.database.teams_channel_destinations.count_documents({}) == 4
    assert (await mongo_manager.database.teams_channel_destinations.find_one(
        {"_id": __import__("bson").ObjectId(sibling["destinationId"])}
    ))["enabled"] is True
    assert (await mongo_manager.database.teams_channel_destinations.find_one(
        {"_id": __import__("bson").ObjectId(other_team["destinationId"])}
    ))["enabled"] is True
    assert (await mongo_manager.database.teams_channel_destinations.find_one(
        {"_id": __import__("bson").ObjectId(other_account["destinationId"])}
    ))["enabled"] is True

    assert (await async_client.post(
        "/api/teams/channel-destinations/ACC-001/not-an-object-id/disconnect"
    )).status_code == 404

    safe = (await async_client.get(
        "/api/teams/channel-destinations/ACC-001"
    )).json()
    summary = next(item for item in safe if item["destinationId"] == first["destinationId"])
    assert summary["connected"] is False
    assert summary["disconnectReason"] == "manual_disconnect"
    internal = (await async_client.get(
        "/api/teams/channel-destinations-internal/ACC-001"
    )).json()
    assert first["destinationId"] in {
        item["destinationId"] for item in internal
    }

    reactivated = (await async_client.post(
        f"/api/teams/channel-destinations/ACC-001/{first['destinationId']}/reconnect"
    )).json()["destination"]
    assert reactivated["destinationId"] == first["destinationId"]
    assert reactivated["enabled"] is True
    assert reactivated["disconnectedAt"] is None
    stored = await mongo_manager.database.teams_channel_destinations.find_one(
        {"_id": __import__("bson").ObjectId(reactivated["destinationId"])}
    )
    assert stored["disconnectReason"] is None
    assert stored["disconnectedAt"] is None
    assert await mongo_manager.database.teams_channel_destinations.count_documents({}) == 4


@pytest.mark.asyncio
async def test_automatic_retry_does_not_reactivate_manual_removal(async_client):
    await map_tenant(async_client, "ACC-001", "TENANT-A")
    created = (await async_client.post(
        "/api/teams/channel-destinations",
        json=destination("TENANT-A", "SALES-ID", "Sales"),
    )).json()["destination"]
    await mongo_manager.database.teams_channel_destinations.update_one(
        {"_id": __import__("bson").ObjectId(created["destinationId"])},
        {"$set": {
            "enabled": False, "disconnectReason": "manual_removal",
            "disconnectSource": "stratsync_ui",
            "disconnectedAt": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ),
        }},
    )

    retried = (await async_client.post(
        "/api/teams/channel-destinations",
        json={
            **destination("TENANT-A", "SALES-ID", "Sales retry"),
            "registrationTrigger": "channel_created",
        },
    )).json()["destination"]

    assert retried["destinationId"] == created["destinationId"]
    assert retried["enabled"] is False
    assert retried["disconnectReason"] == "manual_removal"
    assert await mongo_manager.database.teams_channel_destinations.count_documents({}) == 1


@pytest.mark.asyncio
async def test_reconnect_rejects_team_uninstalled_destination(async_client):
    await map_tenant(async_client, "ACC-001", "TENANT-A")
    created = (await async_client.post(
        "/api/teams/channel-destinations",
        json=destination("TENANT-A", "SALES-ID", "Sales"),
    )).json()["destination"]
    await mongo_manager.database.teams_channel_destinations.update_one(
        {"_id": __import__("bson").ObjectId(created["destinationId"])},
        {"$set": {
            "enabled": False,
            "disconnectReason": "team_uninstalled",
            "disconnectedAt": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ),
        }},
    )

    response = await async_client.post(
        f"/api/teams/channel-destinations/ACC-001/{created['destinationId']}/reconnect"
    )

    assert response.status_code == 409
    assert "Reinstall" in response.json()["detail"]
    stored = await mongo_manager.database.teams_channel_destinations.find_one(
        {"_id": __import__("bson").ObjectId(created["destinationId"])}
    )
    assert stored["enabled"] is False
    assert stored["disconnectReason"] == "team_uninstalled"


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


@pytest.mark.asyncio
async def test_registration_rejects_team_conversation_and_preserves_metadata(async_client):
    await map_tenant(async_client, "ACC-001", "TENANT-A")
    await async_client.post("/api/teams/installations", json={
        "tenantId": "TENANT-A", "teamId": "TEAM-A", "channelId": "T1-ID",
        "conversationId": "TEAM-A", "serviceUrl": "https://example.test/",
        "teamName": "Stratsync.ai", "botAppId": "bot",
    })
    invalid = await async_client.post(
        "/api/teams/channel-destinations",
        json={
            **destination("TENANT-A", "RTEST-ID", "r_test"),
            "teamId": "TEAM-A", "teamName": None, "conversationId": "TEAM-A",
        },
    )
    assert invalid.status_code == 422
    original = (await async_client.post(
        "/api/teams/channel-destinations",
        json={
            **destination("TENANT-A", "RTEST-ID", "r_test"),
            "teamId": "TEAM-A", "teamName": None,
        },
    )).json()["destination"]
    assert original["conversationId"] == "RTEST-ID"
    assert original["teamName"] == "Stratsync.ai"

    refreshed = (await async_client.post(
        "/api/teams/channel-destinations",
        json={
            **destination("TENANT-A", "RTEST-ID", ""),
            "teamId": "TEAM-A", "teamName": None, "channelName": None,
            "conversationId": "RTEST-ID",
        },
    )).json()["destination"]
    assert refreshed["teamName"] == "Stratsync.ai"
    assert refreshed["channelName"] == "r_test"


@pytest.mark.asyncio
async def test_team_name_enrichment_never_crosses_team_or_account(async_client):
    await map_tenant(async_client, "ACC-001", "TENANT-A")
    await map_tenant(async_client, "ACC-002", "TENANT-B")
    for tenant, team, name in (
        ("TENANT-A", "OTHER-TEAM", "Wrong Team"),
        ("TENANT-B", "TEAM-A", "Wrong Account"),
    ):
        await async_client.post("/api/teams/installations", json={
            "tenantId": tenant, "teamId": team, "conversationId": team,
            "serviceUrl": "https://example.test/", "teamName": name, "botAppId": "bot",
        })
    created = (await async_client.post(
        "/api/teams/channel-destinations",
        json={
            **destination("TENANT-A", "CHANNEL-A", "Channel A"),
            "teamId": "TEAM-A", "teamName": None,
        },
    )).json()["destination"]
    assert created["teamName"] is None


@pytest.mark.asyncio
async def test_missing_team_name_uses_exact_team_installation_and_preserves_metadata(
    async_client, sample_risk_payload, monkeypatch
):
    captured = []

    async def trigger(self, url, payload, event_id):
        captured.append(payload)
        return {"success": True}

    monkeypatch.setattr(N8nService, "trigger_webhook", trigger)
    await map_tenant(async_client, "ACC-001", "TENANT-A")
    await async_client.post("/api/risks", json=sample_risk_payload)

    for team_id, team_name in (
        ("TEAM-A", "Stratsync.ai"),
        ("TEAM-B", "rohit-test-channel"),
    ):
        await async_client.post("/api/teams/installations", json={
            "tenantId": "TENANT-A", "teamId": team_id,
            "conversationId": team_id, "serviceUrl": "https://example.test/",
            "teamName": team_name, "botAppId": "bot",
        })

    # Lifecycle state must not make exact-Team display metadata unsafe to reuse.
    await mongo_manager.database.teams_installations.update_one(
        {"accountId": "ACC-001", "tenantId": "TENANT-A", "teamId": "TEAM-B"},
        {"$set": {"enabled": False}},
    )

    created = {}
    for team_id, channel_id, channel_name in (
        ("TEAM-A", "CHANNEL-34", "test34"),
        ("TEAM-A", "CHANNEL-35", "test35"),
        ("TEAM-A", "CHANNEL-36", "test36"),
        ("TEAM-B", "CHANNEL-3", "test3"),
    ):
        payload = destination("TENANT-A", channel_id, channel_name)
        payload.update({"teamId": team_id, "teamName": None})
        response = await async_client.post(
            "/api/teams/channel-destinations", json=payload
        )
        assert response.status_code == 200
        created[channel_id] = response.json()["destination"]

    assert created["CHANNEL-3"]["teamName"] == "rohit-test-channel"
    assert all(
        created[channel_id]["teamName"] == "Stratsync.ai"
        for channel_id in ("CHANNEL-34", "CHANNEL-35", "CHANNEL-36")
    )

    # A later sparse event must preserve both known Team and channel metadata.
    sparse = destination("TENANT-A", "CHANNEL-3", "")
    sparse.update({
        "teamId": "TEAM-B", "teamName": None, "channelName": None,
    })
    refreshed = (await async_client.post(
        "/api/teams/channel-destinations", json=sparse
    )).json()["destination"]
    assert refreshed["teamName"] == "rohit-test-channel"
    assert refreshed["channelName"] == "test3"

    listed = (await async_client.get(
        "/api/teams/channel-destinations/ACC-001"
    )).json()
    assert {(item["teamName"], item["channelName"]) for item in listed} == {
        ("Stratsync.ai", "test34"),
        ("Stratsync.ai", "test35"),
        ("Stratsync.ai", "test36"),
        ("rohit-test-channel", "test3"),
    }

    sent = await async_client.post(
        "/api/risks/RSK-OP-0821/send-to-teams",
        json={"destinationId": created["CHANNEL-3"]["destinationId"]},
    )
    assert sent.status_code == 200
    assert captured[0]["teamsDestination"]["teamId"] == "TEAM-B"
    assert captured[0]["teamsDestination"]["channelId"] == "CHANNEL-3"


@pytest.mark.asyncio
async def test_selected_malformed_destination_is_rejected_without_fabrication(async_client, sample_risk_payload, monkeypatch):
    captured = []

    async def trigger(self, url, payload, event_id):
        captured.append(payload)
        return {"success": True}

    monkeypatch.setattr(N8nService, "trigger_webhook", trigger)
    await map_tenant(async_client, "ACC-001", "TENANT-A")
    await async_client.post("/api/risks", json=sample_risk_payload)
    created = (await async_client.post(
        "/api/teams/channel-destinations",
        json=destination("TENANT-A", "RTEST-ID", "r_test"),
    )).json()["destination"]
    await mongo_manager.database.teams_channel_destinations.update_one(
        {"channelId": "RTEST-ID"}, {"$set": {"conversationId": "team-TENANT-A"}},
    )
    sent = await async_client.post(
        "/api/risks/RSK-OP-0821/send-to-teams",
        json={"destinationId": created["destinationId"]},
    )
    assert sent.status_code == 404
    assert captured == []
    stored = await mongo_manager.database.teams_channel_destinations.find_one(
        {"channelId": "RTEST-ID"}
    )
    assert stored["conversationId"] == "team-TENANT-A"


@pytest.mark.asyncio
async def test_repair_script_dry_run_apply_scope_and_idempotency(async_client):
    await map_tenant(async_client, "ACC-001", "TENANT-A")
    await map_tenant(async_client, "ACC-002", "TENANT-B")
    await async_client.post("/api/teams/installations", json={
        "tenantId": "TENANT-A", "teamId": "TEAM-A", "conversationId": "TEAM-A",
        "serviceUrl": "https://example.test/", "teamName": "Stratsync.ai", "botAppId": "bot",
    })
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    documents = [
        {"accountId": "ACC-001", "tenantId": "TENANT-A", "teamId": "TEAM-A",
         "channelId": "T1-ID", "conversationId": "T1-ID", "channelName": "t1",
         "enabled": True, "serviceUrl": "https://example.test/", "createdAt": now, "updatedAt": now},
        {"accountId": "ACC-001", "tenantId": "TENANT-A", "teamId": "TEAM-A",
         "channelId": "RTEST-ID", "conversationId": "TEAM-A", "channelName": "r_test",
         "enabled": True, "serviceUrl": "https://example.test/", "createdAt": now, "updatedAt": now},
        {"accountId": "ACC-002", "tenantId": "TENANT-B", "teamId": "TEAM-B",
         "channelId": "OTHER-ID", "conversationId": "OTHER-ID", "enabled": True,
         "serviceUrl": "https://example.test/", "createdAt": now, "updatedAt": now},
    ]
    await mongo_manager.database.teams_channel_destinations.insert_many(documents)
    dry = await repair_teams_channel_conversations(mongo_manager.database, apply=False)
    assert [item["channelId"] for item in dry] == ["RTEST-ID"]
    malformed = await mongo_manager.database.teams_channel_destinations.find_one({"channelId": "RTEST-ID"})
    assert malformed["conversationId"] == "TEAM-A" and malformed.get("teamName") is None

    applied = await repair_teams_channel_conversations(mongo_manager.database, apply=True)
    assert len(applied) == 1
    repaired = await mongo_manager.database.teams_channel_destinations.find_one({"channelId": "RTEST-ID"})
    assert repaired["conversationId"] == "RTEST-ID"
    assert repaired["teamName"] == "Stratsync.ai"
    assert await repair_teams_channel_conversations(mongo_manager.database, apply=True) == []
    correct = await mongo_manager.database.teams_channel_destinations.find_one({"channelId": "T1-ID"})
    assert correct["conversationId"] == "T1-ID"
