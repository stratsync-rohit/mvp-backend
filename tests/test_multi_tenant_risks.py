import pytest

from app.services.n8n_service import N8nService


def _risk(base, account_id, risk_id, title):
    payload = {**base, "accountId": account_id, "riskId": risk_id, "title": title}
    payload["entity"] = {**base["entity"]}
    return payload


async def _create(async_client, payload, account_id):
    return await async_client.post("/api/risks", params={"accountId": account_id}, json=payload)


async def _map_and_install(async_client, account_id, tenant_id, team_id):
    await async_client.put(f"/api/teams/tenant-mappings/{account_id}", json={
        "tenantId": tenant_id, "clientName": account_id, "enabled": True})
    await async_client.post("/api/teams/installations", json={
        "tenantId": tenant_id, "teamId": team_id, "channelId": f"channel-{account_id}",
        "conversationId": f"conversation-{account_id}", "serviceUrl": "https://example.test/",
        "botAppId": "bot"})


@pytest.mark.asyncio
async def test_crud_is_strictly_account_scoped_and_duplicate_ids_are_allowed(
    async_client, sample_risk_payload
):
    risk_a = _risk(sample_risk_payload, "ACC-001", "RSK-001", "Shipping Risk")
    risk_b = _risk(sample_risk_payload, "ACC-002", "RSK-001", "Retail Risk")
    assert (await _create(async_client, risk_a, "ACC-001")).status_code == 201
    assert (await _create(async_client, risk_b, "ACC-002")).status_code == 201

    list_a = await async_client.get("/api/risks", params={"accountId": "ACC-001"})
    list_b = await async_client.get("/api/risks", params={"accountId": "ACC-002"})
    assert [item["title"] for item in list_a.json()] == ["Shipping Risk"]
    assert [item["title"] for item in list_b.json()] == ["Retail Risk"]

    assert (await async_client.get("/api/risks/RSK-001", params={"accountId": "ACC-001"})).json()["title"] == "Shipping Risk"
    assert (await async_client.get("/api/risks/RSK-001", params={"accountId": "ACC-002"})).json()["title"] == "Retail Risk"

    unique_b = _risk(sample_risk_payload, "ACC-002", "RSK-B-002", "Supplier Risk")
    await _create(async_client, unique_b, "ACC-002")
    assert (await async_client.get("/api/risks/RSK-B-002", params={"accountId": "ACC-001"})).status_code == 404
    assert (await async_client.patch("/api/risks/RSK-B-002", params={"accountId": "ACC-001"}, json={"title": "Stolen"})).status_code == 404
    assert (await async_client.delete("/api/risks/RSK-B-002", params={"accountId": "ACC-001"})).status_code == 404
    assert (await async_client.get("/api/risks/RSK-B-002", params={"accountId": "ACC-002"})).json()["title"] == "Supplier Risk"


@pytest.mark.asyncio
async def test_client_creation_overrides_injected_account(async_client, sample_risk_payload):
    payload = _risk(sample_risk_payload, "ACC-002", "RSK-INJECT", "Injection attempt")
    created = await _create(async_client, payload, "ACC-001")
    assert created.status_code == 201
    assert created.json()["accountId"] == "ACC-001"
    assert (await async_client.get("/api/risks/RSK-INJECT", params={"accountId": "ACC-002"})).status_code == 404


@pytest.mark.asyncio
async def test_send_to_teams_never_crosses_accounts(async_client, sample_risk_payload, monkeypatch):
    captured = []

    async def trigger(self, url, payload, event_id):
        captured.append(payload)
        return {"status": "received"}

    monkeypatch.setattr(N8nService, "trigger_webhook", trigger)
    risk_b = _risk(sample_risk_payload, "ACC-002", "RSK-B-002", "Supplier Risk")
    await _create(async_client, risk_b, "ACC-002")
    await _map_and_install(async_client, "ACC-001", "TENANT-A", "TEAM-A")

    cross = await async_client.post(
        "/api/risks/RSK-B-002/send-to-teams", params={"accountId": "ACC-001"})
    assert cross.status_code == 404
    no_fallback = await async_client.post(
        "/api/risks/RSK-B-002/send-to-teams", params={"accountId": "ACC-002"})
    assert no_fallback.status_code == 409
    assert captured == []

    await _map_and_install(async_client, "ACC-002", "TENANT-B", "TEAM-B")
    sent = await async_client.post(
        "/api/risks/RSK-B-002/send-to-teams", params={"accountId": "ACC-002"})
    assert sent.status_code == 200
    assert captured[0]["accountId"] == "ACC-002"
    assert captured[0]["teamsDestination"]["tenantId"] == "TENANT-B"
    assert captured[0]["teamsDestination"]["teamId"] == "TEAM-B"


@pytest.mark.asyncio
@pytest.mark.parametrize("action_key", ["view_details", "mitigation_plan"])
async def test_internal_actions_resolve_account_from_tenant_mapping(
    async_client, sample_risk_payload, action_key
):
    risk_a = _risk(sample_risk_payload, "ACC-001", "RSK-001", "Shipping Risk")
    risk_b = _risk(sample_risk_payload, "ACC-002", "RSK-001", "Retail Risk")
    await _create(async_client, risk_a, "ACC-001")
    await _create(async_client, risk_b, "ACC-002")
    await _map_and_install(async_client, "ACC-001", "TENANT-A", "TEAM-A")
    await _map_and_install(async_client, "ACC-002", "TENANT-B", "TEAM-B")

    response_a = await async_client.post("/api/risk-actions/execute", json={
        "riskId": "RSK-001", "actionKey": action_key, "tenantId": "TENANT-A"})
    response_b = await async_client.post("/api/risk-actions/execute", json={
        "riskId": "RSK-001", "actionKey": action_key, "tenantId": "TENANT-B"})
    assert response_a.status_code == response_b.status_code == 200
    assert response_a.json()["data"]["subtitle"] == "Shipping Risk"
    assert response_b.json()["data"]["subtitle"] == "Retail Risk"

    missing_context = await async_client.post("/api/risk-actions/execute", json={
        "riskId": "RSK-001", "actionKey": action_key})
    assert missing_context.status_code == 422
