from datetime import datetime

import pytest

from app.database import mongo_manager


@pytest.mark.asyncio
@pytest.mark.parametrize("entity_type", ["vessel", "sku", "supplier", "future_asset_type"])
async def test_generic_entities_and_sections_round_trip(async_client, sample_risk_payload, entity_type):
    sample_risk_payload["riskId"] = f"RSK-{entity_type}"
    sample_risk_payload["entity"].update(type=entity_type, id=f"ID-{entity_type}")
    response = await async_client.post("/api/risks", json=sample_risk_payload)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["entity"]["type"] == entity_type
    assert body["entity"]["data"]["imo"] == "1234567"
    assert body["metrics"][0]["data"]["currency"] == "USD"
    assert [section["type"] for section in body["details"]["sections"]] == [
        "facts", "bullets", "future_chart"]
    assert body["details"]["sections"][2]["series"] == [1, 2, 3]
    assert body["mitigation"]["sections"][0]["type"] == "steps"
    assert body["createdAt"] == body["updatedAt"]
    assert "_id" not in body


@pytest.mark.asyncio
async def test_dynamic_table_section_round_trip(async_client, sample_risk_payload):
    table = {"type": "table", "title": "Suppliers", "columns": ["Supplier", "OTD"],
             "rows": [["A1", "96%"]]}
    sample_risk_payload["details"]["sections"] = [table]
    body = (await async_client.post("/api/risks", json=sample_risk_payload)).json()
    assert body["details"]["sections"] == [table]


@pytest.mark.asyncio
async def test_patch_preserves_created_at_and_protects_fields(async_client, sample_risk_payload):
    created = (await async_client.post("/api/risks", json=sample_risk_payload)).json()
    response = await async_client.patch("/api/risks/RSK-OP-0821", json={
        "status": "investigating", "metadata": {"nested": {"dynamic": True}}})
    assert response.status_code == 200
    body = response.json()
    assert body["createdAt"] == created["createdAt"]
    assert body["updatedAt"] > created["updatedAt"]
    assert body["metadata"]["nested"]["dynamic"] is True
    protected = await async_client.patch("/api/risks/RSK-OP-0821", json={
        "riskId": "changed", "createdAt": datetime.now().isoformat()})
    assert protected.status_code == 422


@pytest.mark.asyncio
async def test_notification_route_create_and_patch_normalize(async_client, sample_risk_payload):
    sample_risk_payload["notificationRoute"] = "  Risk Alerts  "
    created = await async_client.post("/api/risks", json=sample_risk_payload)
    assert created.status_code == 201
    assert created.json()["notificationRoute"] == "risk-alerts"

    updated = await async_client.patch(
        "/api/risks/RSK-OP-0821", json={"notificationRoute": "Executive_Team"}
    )
    assert updated.status_code == 200
    assert updated.json()["notificationRoute"] == "executive_team"
    assert (await async_client.patch(
        "/api/risks/RSK-OP-0821", json={"accountId": "ACC-002"}
    )).status_code == 422


@pytest.mark.asyncio
async def test_invalid_or_empty_notification_route_rejected(async_client, sample_risk_payload):
    for route in ("   ", "finance/other"):
        sample_risk_payload["notificationRoute"] = route
        response = await async_client.post("/api/risks", json=sample_risk_payload)
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_legacy_document_normalizes_without_migration(async_client, legacy_risk_document):
    await mongo_manager.database.risks.insert_one(legacy_risk_document)
    response = await async_client.get("/api/risks/RSK-LEGACY")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["entity"] == {"type": "vessel", "id": "V-OLD", "name": "MV Legacy", "data": {}}
    assert body["details"]["sections"] == [
        {"type": "bullets", "title": "Underlying Exposure", "items": ["Exposure"]},
        {"type": "bullets", "title": "Impact", "items": ["Impact"]},
    ]
    assert [s["type"] for s in body["mitigation"]["sections"]] == ["text", "steps"]
    assert body["mitigation"]["sections"][1]["items"][0]["data"] == {}
    stored = await mongo_manager.database.risks.find_one({"riskId": "RSK-LEGACY"})
    assert "entity" not in stored and "mitigationPlan" in stored


@pytest.mark.asyncio
async def test_mixed_old_and_new_documents_list(async_client, sample_risk_payload, legacy_risk_document):
    await async_client.post("/api/risks", json=sample_risk_payload)
    await mongo_manager.database.risks.insert_one(legacy_risk_document)
    response = await async_client.get("/api/risks")
    assert response.status_code == 200, response.text
    assert {item["riskId"] for item in response.json()} == {"RSK-OP-0821", "RSK-LEGACY"}


@pytest.mark.asyncio
async def test_crud_and_filters(async_client, sample_risk_payload):
    assert (await async_client.post("/api/risks", json=sample_risk_payload)).status_code == 201
    assert (await async_client.post("/api/risks", json=sample_risk_payload)).status_code == 409
    listed = await async_client.get("/api/risks", params={"severity": "high", "status": "open"})
    assert len(listed.json()) == 1
    assert (await async_client.get("/api/risks/missing")).status_code == 404
    assert (await async_client.delete("/api/risks/RSK-OP-0821")).json()["success"] is True


async def _install_teams(async_client):
    await async_client.put("/api/teams/tenant-mappings/ACC-001", json={
        "tenantId": "tenant-1", "clientName": "Client A", "enabled": True})
    await async_client.post("/api/teams/installations", json={
        "tenantId": "tenant-1", "teamId": "team", "channelId": "channel",
        "conversationId": "channel", "serviceUrl": "https://example.test/", "botAppId": "bot"})
    return (await async_client.post("/api/teams/channel-destinations", json={
        "tenantId": "tenant-1", "teamId": "team", "channelId": "channel",
        "conversationId": "channel", "serviceUrl": "https://example.test/",
        "teamName": "Team", "channelName": "Channel",
    })).json()["destination"]


@pytest.mark.asyncio
async def test_notification_adapter_and_send_to_teams(async_client, sample_risk_payload, mock_n8n_success):
    await async_client.post("/api/risks", json=sample_risk_payload)
    notification = (await async_client.get("/api/risks/RSK-OP-0821/notification")).json()
    assert notification["entity"]["type"] == "vessel"
    assert notification["metrics"] == sample_risk_payload["metrics"]
    assert notification["status"] == "open"
    assert set(notification) == {
        "riskId", "title", "severity", "status", "summary", "entity", "metrics"}
    assert "details" not in notification and "mitigation" not in notification
    await _install_teams(async_client)
    sent = await async_client.post("/api/risks/RSK-OP-0821/send-to-teams")
    assert sent.status_code == 200 and sent.json()["success"] is True


@pytest.mark.asyncio
async def test_send_to_teams_failures(async_client, sample_risk_payload, mock_n8n_failure):
    await async_client.post("/api/risks", json=sample_risk_payload)
    assert (await async_client.post("/api/risks/RSK-OP-0821/send-to-teams")).status_code == 409
    await _install_teams(async_client)
    assert (await async_client.post("/api/risks/RSK-OP-0821/send-to-teams")).status_code == 502


@pytest.mark.asyncio
async def test_send_to_teams_rejects_inactive_installation(async_client, sample_risk_payload):
    await async_client.post("/api/risks", json=sample_risk_payload)
    await _install_teams(async_client)
    await async_client.post(
        "/api/teams/installations/disconnect",
        json={"tenantId": "tenant-1", "teamId": "team"},
    )
    response = await async_client.post("/api/risks/RSK-OP-0821/send-to-teams")
    assert response.status_code == 409
    assert response.json() == {
        "detail": "Microsoft Teams integration is not connected for this account."
    }


@pytest.mark.asyncio
async def test_manual_disconnect_blocks_send_and_reconnect_restores_same_destination(
    async_client, sample_risk_payload, mock_n8n_success,
):
    await async_client.post("/api/risks", json=sample_risk_payload)
    destination = await _install_teams(async_client)
    destination_id = destination["destinationId"]

    disconnected = await async_client.post(
        f"/api/teams/channel-destinations/ACC-001/{destination_id}/disconnect"
    )
    assert disconnected.status_code == 200
    blocked = await async_client.post(
        "/api/risks/RSK-OP-0821/send-to-teams",
        json={"destinationId": destination_id},
    )
    assert blocked.status_code == 409

    reconnected = await async_client.post(
        f"/api/teams/channel-destinations/ACC-001/{destination_id}/reconnect"
    )
    assert reconnected.status_code == 200
    assert reconnected.json()["destinationId"] == destination_id
    sent = await async_client.post(
        "/api/risks/RSK-OP-0821/send-to-teams",
        json={"destinationId": destination_id},
    )
    assert sent.status_code == 200
    assert sent.json()["success"] is True


@pytest.mark.asyncio
async def test_multiple_installations_without_route_is_controlled(
    async_client, sample_risk_payload, mock_n8n_success
):
    await async_client.post("/api/risks", json=sample_risk_payload)
    await _install_teams(async_client)
    await async_client.post("/api/teams/installations", json={
        "tenantId": "tenant-1", "teamId": "team-2", "channelId": "channel-2",
        "conversationId": "channel-2", "serviceUrl": "https://example.test/", "botAppId": "bot",
    })
    await async_client.post("/api/teams/channel-destinations", json={
        "tenantId": "tenant-1", "teamId": "team-2", "channelId": "channel-2",
        "conversationId": "channel-2", "serviceUrl": "https://example.test/",
    })
    response = await async_client.post("/api/risks/RSK-OP-0821/send-to-teams")
    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Multiple Microsoft Teams channels are connected. destinationId is required."
    )


@pytest.mark.asyncio
async def test_legacy_notification_route_never_selects_a_channel(
    async_client, sample_risk_payload, monkeypatch
):
    captured = []

    async def trigger(self, url, payload, event_id):
        captured.append(payload)
        return {"status": "received"}

    from app.services.n8n_service import N8nService
    monkeypatch.setattr(N8nService, "trigger_webhook", trigger)
    await async_client.put("/api/teams/tenant-mappings/ACC-001", json={
        "tenantId": "tenant-1", "clientName": "Client A", "enabled": True})
    destinations = []
    for suffix in ("finance", "operations"):
        destinations.append((await async_client.post(
            "/api/teams/channel-destinations", json={
                "tenantId": "tenant-1", "teamId": f"team-{suffix}",
                "channelId": f"channel-{suffix}",
                "conversationId": f"channel-{suffix}",
                "serviceUrl": "https://example.test/",
            }
        )).json()["destination"])

    sample_risk_payload["notificationRoute"] = "finance"
    await async_client.post("/api/risks", json=sample_risk_payload)
    sent = await async_client.post(
        "/api/risks/RSK-OP-0821/send-to-teams",
        json={"destinationId": destinations[0]["destinationId"]},
    )
    assert sent.status_code == 200
    assert captured[0]["teamsDestination"]["channelId"] == "channel-finance"

    ambiguous = await async_client.post("/api/risks/RSK-OP-0821/send-to-teams")
    assert ambiguous.status_code == 409
    assert ambiguous.json()["detail"].endswith("destinationId is required.")
    assert len(captured) == 1


@pytest.mark.asyncio
async def test_deprecated_installation_id_does_not_bypass_channel_ambiguity(
    async_client, sample_risk_payload, monkeypatch
):
    captured = []

    async def trigger(self, url, payload, event_id):
        captured.append(payload)
        return {"status": "received"}

    from app.services.n8n_service import N8nService
    monkeypatch.setattr(N8nService, "trigger_webhook", trigger)
    sample_risk_payload["notificationRoute"] = "automatic-route"
    await async_client.post("/api/risks", json=sample_risk_payload)
    await async_client.put("/api/teams/tenant-mappings/ACC-001", json={
        "tenantId": "tenant-a", "clientName": "Client A", "enabled": True,
    })
    await async_client.put("/api/teams/tenant-mappings/ACC-002", json={
        "tenantId": "tenant-b", "clientName": "Client B", "enabled": True,
    })

    for channel in ("sales-channel", "dev-channel"):
        await async_client.post("/api/teams/channel-destinations", json={
            "tenantId": "tenant-a", "teamId": f"team-{channel}",
            "channelId": channel, "conversationId": channel,
            "serviceUrl": "https://example.test/",
        })
    response = await async_client.post(
        "/api/risks/RSK-OP-0821/send-to-teams",
        json={"installationId": "legacy-installation-id"},
    )
    assert response.status_code == 409
    assert response.json()["detail"].endswith("destinationId is required.")
    assert captured == []
