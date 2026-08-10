import pytest


@pytest.mark.asyncio
async def test_view_details_action(async_client, sample_risk_payload):
    await async_client.post("/api/risks", json=sample_risk_payload)

    response = await async_client.post(
        "/api/risk-actions/execute",
        json={"riskId": "RSK-OP-0821", "actionKey": "view_details"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["actionKey"] == "view_details"
    assert body["cardType"] == "risk_details"
    assert body["data"]["fundingShortfall"] == 210000


@pytest.mark.asyncio
async def test_mitigation_plan_action(async_client, sample_risk_payload):
    await async_client.post("/api/risks", json=sample_risk_payload)

    response = await async_client.post(
        "/api/risk-actions/execute",
        json={"riskId": "RSK-OP-0821", "actionKey": "mitigation_plan"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["actionKey"] == "mitigation_plan"
    assert body["cardType"] == "mitigation_plan"
    assert len(body["data"]["steps"]) == 1


@pytest.mark.asyncio
async def test_track_risk_action(async_client, sample_risk_payload):
    await async_client.post("/api/risks", json=sample_risk_payload)

    response = await async_client.post(
        "/api/risk-actions/execute",
        json={
            "riskId": "RSK-OP-0821",
            "actionKey": "track_risk",
            "payload": {"actorName": "manager@example.com"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "success": True,
        "riskId": "RSK-OP-0821",
        "actionKey": "track_risk",
        "message": "Risk tracking enabled",
    }

    # Verify persistence
    risk_response = await async_client.get("/api/risks/RSK-OP-0821")
    assert risk_response.json()["tracking"]["enabled"] is True


@pytest.mark.asyncio
async def test_assign_action(async_client, sample_risk_payload):
    await async_client.post("/api/risks", json=sample_risk_payload)

    response = await async_client.post(
        "/api/risk-actions/execute",
        json={
            "riskId": "RSK-OP-0821",
            "actionKey": "assign",
            "payload": {"assignedTo": "john@example.com", "assignedBy": "manager@example.com"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "john@example.com" in body["message"]

    risk_response = await async_client.get("/api/risks/RSK-OP-0821")
    assert risk_response.json()["assignment"]["assignedTo"] == "john@example.com"


@pytest.mark.asyncio
async def test_action_on_missing_risk_returns_404(async_client):
    response = await async_client.post(
        "/api/risk-actions/execute",
        json={"riskId": "RSK-DOES-NOT-EXIST", "actionKey": "view_details"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Risk not found"


@pytest.mark.asyncio
async def test_assign_without_payload_returns_422(async_client, sample_risk_payload):
    await async_client.post("/api/risks", json=sample_risk_payload)

    response = await async_client.post(
        "/api/risk-actions/execute",
        json={"riskId": "RSK-OP-0821", "actionKey": "assign"},
    )
    assert response.status_code == 422
