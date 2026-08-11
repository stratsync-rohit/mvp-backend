import pytest


@pytest.mark.asyncio
async def test_dynamic_detail_and_mitigation_actions_are_isolated(async_client, sample_risk_payload):
    await async_client.post("/api/risks", json=sample_risk_payload)
    details = (await async_client.post("/api/risk-actions/execute", json={
        "riskId": "RSK-OP-0821", "actionKey": "view_details"})).json()
    mitigation = (await async_client.post("/api/risk-actions/execute", json={
        "riskId": "RSK-OP-0821", "actionKey": "mitigation_plan"})).json()
    assert details["cardType"] == mitigation["cardType"] == "dynamic_card"
    assert details["data"]["title"] == "Risk Details"
    assert mitigation["data"]["title"] == "Mitigation Plan"
    assert details["data"]["sections"] == sample_risk_payload["details"]["sections"]
    assert mitigation["data"]["sections"] == sample_risk_payload["mitigation"]["sections"]


@pytest.mark.asyncio
async def test_empty_action_sections_do_not_crash(async_client, sample_risk_payload):
    sample_risk_payload["details"] = {"sections": []}
    sample_risk_payload["mitigation"] = {"sections": []}
    await async_client.post("/api/risks", json=sample_risk_payload)
    for action in ("view_details", "mitigation_plan"):
        response = await async_client.post("/api/risk-actions/execute", json={
            "riskId": "RSK-OP-0821", "actionKey": action})
        assert response.status_code == 200
        assert response.json()["data"]["sections"] == []


@pytest.mark.asyncio
async def test_track_and_assign_remain_working(async_client, sample_risk_payload):
    await async_client.post("/api/risks", json=sample_risk_payload)
    tracked = await async_client.post("/api/risk-actions/execute", json={
        "riskId": "RSK-OP-0821", "actionKey": "track_risk", "payload": {"actorName": "manager"}})
    assigned = await async_client.post("/api/risk-actions/execute", json={
        "riskId": "RSK-OP-0821", "actionKey": "assign",
        "payload": {"assignedTo": "john", "assignedBy": "manager"}})
    assert tracked.status_code == assigned.status_code == 200
    risk = (await async_client.get("/api/risks/RSK-OP-0821")).json()
    assert risk["tracking"]["enabled"] is True
    assert risk["assignment"]["assignedTo"] == "john"


@pytest.mark.asyncio
async def test_action_errors(async_client, sample_risk_payload):
    missing = await async_client.post("/api/risk-actions/execute", json={
        "riskId": "missing", "actionKey": "view_details"})
    assert missing.status_code == 404
    await async_client.post("/api/risks", json=sample_risk_payload)
    invalid = await async_client.post("/api/risk-actions/execute", json={
        "riskId": "RSK-OP-0821", "actionKey": "assign"})
    assert invalid.status_code == 422
