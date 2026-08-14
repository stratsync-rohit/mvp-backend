import pytest

from app.config import get_settings
from app.services.tenant_mapping_service import TenantMappingService
from app.database import mongo_manager


@pytest.mark.asyncio
async def test_accounts_returns_minimal_metadata_including_disabled(async_client):
    await async_client.put("/api/teams/tenant-mappings/ACC-001", json={
        "tenantId": "TENANT-A", "clientName": "StratSync", "enabled": True})
    await async_client.put("/api/teams/tenant-mappings/ACC-002", json={
        "tenantId": "TENANT-B", "clientName": "Client B", "enabled": False})

    response = await async_client.get("/api/accounts")
    assert response.status_code == 200
    assert response.json() == [
        {"accountId": "ACC-001", "accountName": "StratSync"},
        {"accountId": "ACC-002", "accountName": "Client B"},
    ]
    serialized = repr(response.json()).lower()
    for forbidden in (
        "tenantid", "serviceurl", "conversationid", "channelid", "botappid",
        "connectedby", "apikey", "token", "secret", "authorization",
    ):
        assert forbidden not in serialized


@pytest.mark.asyncio
async def test_accounts_falls_back_to_account_id_when_client_name_is_missing(async_client):
    await mongo_manager.database.tenant_mappings.insert_one({
        "accountId": "ACC-001", "tenantId": "TENANT-A", "enabled": False})
    response = await async_client.get("/api/accounts")
    assert response.json() == [{"accountId": "ACC-001", "accountName": "ACC-001"}]


@pytest.mark.asyncio
async def test_auto_provisioned_account_appears_in_accounts(async_client):
    await async_client.put("/api/teams/tenant-mappings/ACC-001", json={
        "tenantId": "TENANT-A", "clientName": "StratSync", "enabled": True})
    installed = await async_client.post("/api/teams/installations", json={
        "tenantId": "TENANT-B", "teamId": "TEAM-B", "channelId": "CHANNEL-B",
        "conversationId": "CONVERSATION-B", "serviceUrl": "https://example.test/",
        "teamName": "Client B", "botAppId": "bot"})
    assert installed.status_code == 200
    assert installed.json()["installation"]["accountId"] == "ACC-002"
    assert (await async_client.get("/api/accounts")).json() == [
        {"accountId": "ACC-001", "accountName": "StratSync"},
        {"accountId": "ACC-002", "accountName": "Client B"},
    ]


@pytest.mark.asyncio
async def test_account_service_defensively_deduplicates_account_ids():
    class DuplicateRepository:
        async def list_account_metadata(self):
            return [
                {"accountId": "ACC-001"},
                {"accountId": "ACC-001", "clientName": "StratSync"},
                {"accountId": "ACC-002", "clientName": "Client B"},
            ]

    assert await TenantMappingService(DuplicateRepository()).list_accounts() == [
        {"accountId": "ACC-001", "accountName": "StratSync"},
        {"accountId": "ACC-002", "accountName": "Client B"},
    ]


@pytest.mark.asyncio
async def test_admin_integrations_remains_internal_key_protected(async_client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "internal_api_key_enabled", True)
    monkeypatch.setattr(settings, "internal_api_key", "test-only-key")

    unauthorized = await async_client.get("/api/teams/integrations")
    assert unauthorized.status_code == 401
    assert unauthorized.json() == {"detail": "Invalid or missing internal API key"}
    assert (await async_client.get("/api/accounts")).status_code == 200
    authorized = await async_client.get(
        "/api/teams/integrations", headers={"X-Internal-API-Key": "test-only-key"})
    assert authorized.status_code == 200
