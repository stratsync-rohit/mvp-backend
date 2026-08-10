import pytest


@pytest.mark.asyncio
async def test_create_risk(async_client, sample_risk_payload):
    response = await async_client.post("/api/risks", json=sample_risk_payload)
    assert response.status_code == 201
    body = response.json()
    assert body["riskId"] == "RSK-OP-0821"
    assert body["title"] == "Owner funding is short"
    assert "_id" not in body


@pytest.mark.asyncio
async def test_create_duplicate_risk_returns_409(async_client, sample_risk_payload):
    first = await async_client.post("/api/risks", json=sample_risk_payload)
    assert first.status_code == 201

    second = await async_client.post("/api/risks", json=sample_risk_payload)
    assert second.status_code == 409
    assert second.json()["detail"] == "Risk already exists"


@pytest.mark.asyncio
async def test_get_risk(async_client, sample_risk_payload):
    await async_client.post("/api/risks", json=sample_risk_payload)

    response = await async_client.get("/api/risks/RSK-OP-0821")
    assert response.status_code == 200
    assert response.json()["riskId"] == "RSK-OP-0821"


@pytest.mark.asyncio
async def test_get_risk_not_found(async_client):
    response = await async_client.get("/api/risks/RSK-DOES-NOT-EXIST")
    assert response.status_code == 404
    assert response.json()["detail"] == "Risk not found"


@pytest.mark.asyncio
async def test_list_risks_with_filters(async_client, sample_risk_payload):
    await async_client.post("/api/risks", json=sample_risk_payload)

    response = await async_client.get("/api/risks", params={"severity": "high", "status": "open"})
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["riskId"] == "RSK-OP-0821"


@pytest.mark.asyncio
async def test_update_risk_partial(async_client, sample_risk_payload):
    await async_client.post("/api/risks", json=sample_risk_payload)

    response = await async_client.patch("/api/risks/RSK-OP-0821", json={"status": "in_progress"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "in_progress"
    # riskId must remain unchanged
    assert body["riskId"] == "RSK-OP-0821"


@pytest.mark.asyncio
async def test_delete_risk(async_client, sample_risk_payload):
    await async_client.post("/api/risks", json=sample_risk_payload)

    response = await async_client.delete("/api/risks/RSK-OP-0821")
    assert response.status_code == 200
    assert response.json() == {"success": True, "riskId": "RSK-OP-0821"}

    follow_up = await async_client.get("/api/risks/RSK-OP-0821")
    assert follow_up.status_code == 404


@pytest.mark.asyncio
async def test_notification_payload(async_client, sample_risk_payload):
    await async_client.post("/api/risks", json=sample_risk_payload)

    response = await async_client.get("/api/risks/RSK-OP-0821/notification")
    assert response.status_code == 200
    body = response.json()
    assert body["riskId"] == "RSK-OP-0821"
    assert body["vessel"]["name"] == "MV Ocean Pioneer"
    action_keys = {a["key"] for a in body["actions"]}
    assert action_keys == {"view_details", "mitigation_plan", "assign", "track_risk"}
    # Must NOT contain Adaptive Card JSON or internal fields
    assert "fundingShortfall" not in body
    assert "mitigationPlan" not in body


@pytest.mark.asyncio
async def test_details_payload(async_client, sample_risk_payload):
    await async_client.post("/api/risks", json=sample_risk_payload)

    response = await async_client.get("/api/risks/RSK-OP-0821/details")
    assert response.status_code == 200
    body = response.json()
    assert body["fundingShortfall"] == 210000
    assert body["paymentsAtRisk"] == 210000
    assert isinstance(body["underlyingExposure"], list)


@pytest.mark.asyncio
async def test_mitigation_plan_payload(async_client, sample_risk_payload):
    await async_client.post("/api/risks", json=sample_risk_payload)

    response = await async_client.get("/api/risks/RSK-OP-0821/mitigation-plan")
    assert response.status_code == 200
    body = response.json()
    assert body["summary"] == "Secure additional funding and prioritise critical payments."
    assert len(body["steps"]) == 1


@pytest.mark.asyncio
async def test_send_to_teams_success(
    async_client, sample_risk_payload, sample_destination_payload, mock_n8n_success
):
    await async_client.post("/api/risks", json=sample_risk_payload)
    await async_client.put("/api/teams/destinations/ACC-001", json=sample_destination_payload)

    response = await async_client.post("/api/risks/RSK-OP-0821/send-to-teams")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["riskId"] == "RSK-OP-0821"
    assert "eventId" in body


@pytest.mark.asyncio
async def test_send_to_teams_missing_destination_returns_404(
    async_client, sample_risk_payload, mock_n8n_success
):
    await async_client.post("/api/risks", json=sample_risk_payload)

    response = await async_client.post("/api/risks/RSK-OP-0821/send-to-teams")
    assert response.status_code == 404
    assert response.json()["detail"] == "Teams destination not configured"


@pytest.mark.asyncio
async def test_send_to_teams_n8n_failure_returns_502(
    async_client, sample_risk_payload, sample_destination_payload, mock_n8n_failure
):
    await async_client.post("/api/risks", json=sample_risk_payload)
    await async_client.put("/api/teams/destinations/ACC-001", json=sample_destination_payload)

    response = await async_client.post("/api/risks/RSK-OP-0821/send-to-teams")
    assert response.status_code == 502
    assert response.json()["detail"] == "Unable to queue Microsoft Teams notification"


@pytest.mark.asyncio
async def test_put_teams_destination_upsert(async_client, sample_destination_payload):
    response = await async_client.put(
        "/api/teams/destinations/ACC-001", json=sample_destination_payload
    )
    assert response.status_code == 200
    body = response.json()
    assert body["accountId"] == "ACC-001"
    assert body["teamId"] == "19:sample-team-id"
