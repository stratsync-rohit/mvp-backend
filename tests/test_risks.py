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
        "conversationId": "conversation", "serviceUrl": "https://example.test/", "botAppId": "bot"})


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
