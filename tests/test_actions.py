import pytest


async def _map_tenant(async_client, account_id="ACC-001", tenant_id="tenant-1"):
    await async_client.put(f"/api/teams/tenant-mappings/{account_id}", json={
        "tenantId": tenant_id, "clientName": account_id, "enabled": True})


def _action(risk_id, action_key, payload=None, tenant_id="tenant-1"):
    body = {"riskId": risk_id, "actionKey": action_key, "tenantId": tenant_id}
    if payload is not None:
        body["payload"] = payload
    return body


@pytest.mark.asyncio
async def test_dynamic_detail_and_mitigation_actions_are_isolated(async_client, sample_risk_payload):
    await _map_tenant(async_client)
    await async_client.post("/api/risks", json=sample_risk_payload)
    details = (await async_client.post("/api/risk-actions/execute", json={
        **_action("RSK-OP-0821", "view_details")})).json()
    mitigation = (await async_client.post("/api/risk-actions/execute", json={
        **_action("RSK-OP-0821", "mitigation_plan")})).json()
    assert details["cardType"] == mitigation["cardType"] == "dynamic_card"
    assert details["data"]["title"] == "Risk Details"
    assert mitigation["data"]["title"] == "Mitigation Plan"
    assert details["data"]["sections"] == sample_risk_payload["details"]["sections"]
    assert mitigation["data"]["sections"] == sample_risk_payload["mitigation"]["sections"]


@pytest.mark.asyncio
async def test_empty_action_sections_do_not_crash(async_client, sample_risk_payload):
    await _map_tenant(async_client)
    sample_risk_payload["details"] = {"sections": []}
    sample_risk_payload["mitigation"] = {"sections": []}
    await async_client.post("/api/risks", json=sample_risk_payload)
    for action in ("view_details", "mitigation_plan"):
        response = await async_client.post("/api/risk-actions/execute", json={
            **_action("RSK-OP-0821", action)})
        assert response.status_code == 200
        assert response.json()["data"]["sections"] == []


@pytest.mark.asyncio
async def test_track_and_assign_remain_working(async_client, sample_risk_payload):
    await _map_tenant(async_client)
    await async_client.post("/api/risks", json=sample_risk_payload)
    tracked = await async_client.post("/api/risk-actions/execute", json={
        **_action("RSK-OP-0821", "track_risk", {"actorName": "manager"})})
    assigned = await async_client.post("/api/risk-actions/execute", json={
        **_action("RSK-OP-0821", "assign", {"assignedTo": "john", "assignedBy": "manager"})})
    assert tracked.status_code == assigned.status_code == 200
    risk = (await async_client.get("/api/risks/RSK-OP-0821")).json()
    assert risk["tracking"]["enabled"] is True
    assert risk["assignment"]["assignedTo"] == "john"


@pytest.mark.asyncio
async def test_action_errors(async_client, sample_risk_payload):
    await _map_tenant(async_client)
    missing = await async_client.post("/api/risk-actions/execute", json={
        **_action("missing", "view_details")})
    assert missing.status_code == 404
    await async_client.post("/api/risks", json=sample_risk_payload)
    invalid = await async_client.post("/api/risk-actions/execute", json={
        **_action("RSK-OP-0821", "assign")})
    assert invalid.status_code == 422
