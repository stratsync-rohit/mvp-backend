import pytest


INSTALLATION = {
    "tenantId": "tenant-1",
    "teamId": "team-1",
    "channelId": None,
    "conversationId": "conversation-1",
    "serviceUrl": "https://smba.trafficmanager.net/emea/",
    "teamName": None,
    "channelName": None,
    "botAppId": "bot-app-1",
    "enabled": True,
}


async def create_mapping(async_client, account_id="ACC-001", tenant_id="tenant-1"):
    return await async_client.put(
        f"/api/teams/tenant-mappings/{account_id}",
        json={"tenantId": tenant_id, "clientName": "Client A", "enabled": True},
    )


@pytest.mark.asyncio
async def test_tenant_mapping_upsert_and_lookup(async_client):
    created = await create_mapping(async_client)
    assert created.status_code == 200
    assert created.json()["mapping"]["accountId"] == "ACC-001"

    by_account = await async_client.get("/api/teams/tenant-mappings/ACC-001")
    assert by_account.status_code == 200
    assert by_account.json()["tenantId"] == "tenant-1"

    by_tenant = await async_client.get("/api/teams/tenant-mappings/by-tenant/tenant-1")
    assert by_tenant.status_code == 200
    assert by_tenant.json()["accountId"] == "ACC-001"


@pytest.mark.asyncio
async def test_installation_registration_upserts(async_client):
    await create_mapping(async_client)
    first = await async_client.post("/api/teams/installations", json=INSTALLATION)
    assert first.status_code == 200
    created_at = first.json()["installation"]["createdAt"]

    updated_payload = {**INSTALLATION, "teamName": "Operations"}
    second = await async_client.post("/api/teams/installations", json=updated_payload)
    assert second.status_code == 200
    assert second.json()["installation"]["createdAt"] == created_at
    assert second.json()["installation"]["teamName"] == "Operations"
    assert second.json()["installation"]["accountId"] == "ACC-001"

    listed = await async_client.get("/api/teams/installations/ACC-001")
    assert len(listed.json()) == 1


@pytest.mark.asyncio
async def test_integration_status_connected_and_unknown(async_client):
    await create_mapping(async_client)
    await async_client.post("/api/teams/installations", json=INSTALLATION)

    connected = await async_client.get("/api/teams/integration/ACC-001")
    assert connected.status_code == 200
    assert connected.json()["connected"] is True
    assert connected.json()["conversationId"] == "conversation-1"

    unknown = await async_client.get("/api/teams/integration/ACC-999")
    assert unknown.status_code == 200
    assert unknown.json() == {
        "connected": False,
        "accountId": "ACC-999",
        "enabled": False,
    }


@pytest.mark.asyncio
async def test_installation_for_unmapped_tenant_returns_conflict(async_client):
    response = await async_client.post("/api/teams/installations", json=INSTALLATION)
    assert response.status_code == 409
    assert response.json() == {
        "detail": "Microsoft tenant is not mapped to a StratSync account."
    }
