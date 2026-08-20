import asyncio

import pytest

from app.database import mongo_manager


INSTALLATION = {
    "tenantId": "tenant-1",
    "teamId": "team-1",
    "channelId": None,
    "conversationId": "conversation-1",
    "serviceUrl": "https://smba.trafficmanager.net/emea/",
    "teamName": None,
    "channelName": None,
    "connectedByName": None,
    "connectedById": None,
    "connectedByAadObjectId": None,
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
async def test_registration_stores_channel_and_connected_actor(async_client):
    await create_mapping(async_client)
    payload = {
        **INSTALLATION,
        "channelId": "channel-1",
        "channelName": "General",
        "connectedByName": "Installation Actor",
        "connectedById": "teams-user-1",
        "connectedByAadObjectId": "aad-1",
    }
    body = (await async_client.post("/api/teams/installations", json=payload)).json()
    installation = body["installation"]
    assert installation["channelName"] == "General"
    assert installation["connectedByName"] == "Installation Actor"
    assert installation["connectedByAadObjectId"] == "aad-1"


@pytest.mark.asyncio
async def test_sparse_reactivation_preserves_useful_optional_metadata(async_client):
    await create_mapping(async_client)
    rich = {
        **INSTALLATION,
        "channelName": "General",
        "connectedByName": "Installation Actor",
    }
    await async_client.post("/api/teams/installations", json=rich)
    await async_client.post(
        "/api/teams/installations/disconnect",
        json={"tenantId": "tenant-1", "teamId": "team-1"},
    )
    sparse = {key: value for key, value in INSTALLATION.items() if value is not None}
    reactivated = (await async_client.post("/api/teams/installations", json=sparse)).json()
    assert reactivated["installation"]["channelName"] == "General"
    assert reactivated["installation"]["connectedByName"] == "Installation Actor"


@pytest.mark.asyncio
async def test_integration_status_connected_and_unknown(async_client):
    await create_mapping(async_client)
    await async_client.post("/api/teams/installations", json=INSTALLATION)

    connected = await async_client.get("/api/teams/integration/ACC-001")
    assert connected.status_code == 200
    assert connected.json()["connected"] is True
    assert connected.json()["conversationId"] is None
    assert connected.json()["accountName"] == "Client A"
    assert connected.json()["channelName"] is None
    assert connected.json()["connectedByName"] is None

    unknown = await async_client.get("/api/teams/integration/ACC-999")
    assert unknown.status_code == 200
    assert unknown.json()["connected"] is False
    assert unknown.json()["accountId"] == "ACC-999"
    assert unknown.json()["channelName"] is None
    assert unknown.json()["connectedByName"] is None

    forbidden = {
        "serviceUrl", "accessToken", "clientSecret", "botAppId",
        "authorization", "apiKey", "connectedById", "connectedByAadObjectId",
    }
    assert not forbidden.intersection(connected.json())


@pytest.mark.asyncio
async def test_installation_for_unmapped_tenant_auto_provisions(async_client):
    await create_mapping(async_client)
    payload = {**INSTALLATION, "tenantId": "tenant-2", "teamName": "Client B"}
    response = await async_client.post("/api/teams/installations", json=payload)
    assert response.status_code == 200
    assert response.json()["installation"]["accountId"] == "ACC-002"

    mapping = await mongo_manager.database.tenant_mappings.find_one(
        {"tenantId": "tenant-2"}
    )
    assert mapping["accountId"] == "ACC-002"
    assert mapping["clientName"] == "Client B"
    assert mapping["enabled"] is True


@pytest.mark.asyncio
async def test_auto_provision_uses_max_existing_suffix_and_reuses_account(async_client):
    await create_mapping(async_client)
    await create_mapping(async_client, "ACC-003", "tenant-3")
    payload = {**INSTALLATION, "tenantId": "tenant-4", "teamName": None}
    first = await async_client.post("/api/teams/installations", json=payload)
    second = await async_client.post("/api/teams/installations", json=payload)
    assert first.json()["installation"]["accountId"] == "ACC-004"
    assert second.json()["installation"]["accountId"] == "ACC-004"
    assert await mongo_manager.database.tenant_mappings.count_documents(
        {"tenantId": "tenant-4"}
    ) == 1
    mapping = await mongo_manager.database.tenant_mappings.find_one(
        {"tenantId": "tenant-4"}
    )
    assert mapping["clientName"] == "ACC-004"


@pytest.mark.asyncio
async def test_concurrent_new_tenant_registrations_converge(async_client):
    await create_mapping(async_client)
    payload = {**INSTALLATION, "tenantId": "tenant-race", "teamName": "Race Team"}
    first, second = await asyncio.gather(
        async_client.post("/api/teams/installations", json=payload),
        async_client.post("/api/teams/installations", json=payload),
    )
    assert first.status_code == second.status_code == 200
    assert first.json()["installation"]["accountId"] == second.json()["installation"]["accountId"]
    assert await mongo_manager.database.tenant_mappings.count_documents(
        {"tenantId": "tenant-race"}
    ) == 1


@pytest.mark.asyncio
async def test_disabled_mapping_is_not_reprovisioned(async_client):
    await async_client.put(
        "/api/teams/tenant-mappings/ACC-002",
        json={"tenantId": "tenant-2", "clientName": "Client B", "enabled": False},
    )
    response = await async_client.post(
        "/api/teams/installations", json={**INSTALLATION, "tenantId": "tenant-2"}
    )
    assert response.status_code == 409
    assert response.json() == {"detail": "Microsoft tenant mapping is disabled."}
    assert await mongo_manager.database.tenant_mappings.count_documents(
        {"tenantId": "tenant-2"}
    ) == 1


@pytest.mark.asyncio
async def test_disconnect_marks_only_matching_client_inactive(async_client):
    await create_mapping(async_client, "ACC-A", "TENANT-A")
    await create_mapping(async_client, "ACC-B", "TENANT-B")
    install_a = {**INSTALLATION, "tenantId": "TENANT-A", "teamId": "TEAM-A"}
    install_b = {**INSTALLATION, "tenantId": "TENANT-B", "teamId": "TEAM-B"}
    assert (await async_client.post("/api/teams/installations", json=install_a)).status_code == 200
    assert (await async_client.post("/api/teams/installations", json=install_b)).status_code == 200

    response = await async_client.post(
        "/api/teams/installations/disconnect",
        json={"tenantId": "TENANT-A", "teamId": "TEAM-A"},
    )
    assert response.status_code == 200
    assert response.json()["disconnected"] is True
    assert response.json()["accountId"] == "ACC-A"

    stored_a = await mongo_manager.database.teams_installations.find_one(
        {"accountId": "ACC-A", "tenantId": "TENANT-A", "teamId": "TEAM-A"}
    )
    stored_b = await mongo_manager.database.teams_installations.find_one(
        {"accountId": "ACC-B", "tenantId": "TENANT-B", "teamId": "TEAM-B"}
    )
    assert stored_a["enabled"] is False
    assert stored_a["disconnectedAt"] is not None
    assert stored_a.get("teamName") == install_a.get("teamName")
    assert stored_b["enabled"] is True
    assert (await async_client.get("/api/teams/integration/ACC-A")).json()["connected"] is False
    assert (await async_client.get("/api/teams/integration/ACC-B")).json()["connected"] is True


@pytest.mark.asyncio
async def test_disconnect_not_found_is_controlled_and_requires_identity(async_client):
    await create_mapping(async_client)
    missing = await async_client.post(
        "/api/teams/installations/disconnect",
        json={"tenantId": "tenant-1", "teamId": "missing"},
    )
    assert missing.status_code == 200
    assert missing.json()["disconnected"] is False
    invalid = await async_client.post(
        "/api/teams/installations/disconnect", json={"tenantId": "tenant-1"}
    )
    assert invalid.status_code == 422


@pytest.mark.asyncio
async def test_reinstall_reactivates_and_clears_disconnect_timestamp(async_client):
    await create_mapping(async_client)
    first = (await async_client.post("/api/teams/installations", json=INSTALLATION)).json()
    created_at = first["installation"]["createdAt"]
    await async_client.post(
        "/api/teams/installations/disconnect",
        json={"tenantId": "tenant-1", "teamId": "team-1"},
    )
    reinstalled = await async_client.post(
        "/api/teams/installations",
        json={**INSTALLATION, "serviceUrl": "https://new.example.test/", "enabled": False},
    )
    body = reinstalled.json()["installation"]
    assert body["createdAt"] == created_at
    assert body["enabled"] is True
    assert body["disconnectedAt"] is None
    assert body["connectedAt"] is not None
    assert body["serviceUrl"] == "https://new.example.test/"
    assert (await async_client.get("/api/teams/integration/ACC-001")).json()["connected"] is True


@pytest.mark.asyncio
async def test_integration_overview_uses_client_name_and_hides_sensitive_fields(async_client):
    await create_mapping(async_client, "ACC-A", "TENANT-A")
    await mongo_manager.database.tenant_mappings.insert_one(
        {
            "accountId": "ACC-B",
            "tenantId": "TENANT-B",
            "enabled": True,
            "createdAt": (await mongo_manager.database.tenant_mappings.find_one(
                {"accountId": "ACC-A"}
            ))["createdAt"],
            "updatedAt": (await mongo_manager.database.tenant_mappings.find_one(
                {"accountId": "ACC-A"}
            ))["updatedAt"],
        }
    )
    await async_client.post(
        "/api/teams/installations",
        json={
            **INSTALLATION,
            "tenantId": "TENANT-A",
            "teamName": "Operations",
            "channelName": "General",
            "connectedByName": "Installation Actor",
        },
    )
    await async_client.post("/api/teams/channel-destinations", json={
        "tenantId": "TENANT-A", "teamId": "team-1", "teamName": "Operations",
        "channelId": "channel-1", "channelName": "General",
        "conversationId": "conversation-1", "serviceUrl": "https://example.test/",
    })
    response = await async_client.get("/api/teams/integrations")
    assert response.status_code == 200
    items = {item["accountId"]: item for item in response.json()}
    assert items["ACC-A"]["accountName"] == "Client A"
    assert items["ACC-A"]["connected"] is True
    assert items["ACC-A"]["activeInstallations"] == 1
    assert items["ACC-A"]["teamName"] == "Operations"
    assert items["ACC-A"]["channelName"] == "General"
    assert items["ACC-A"]["connectedByName"] == "Installation Actor"
    assert items["ACC-B"]["accountName"] == "ACC-B"
    assert items["ACC-B"]["connected"] is False
    assert items["ACC-B"]["activeInstallations"] == 0
    forbidden = {"serviceUrl", "accessToken", "clientSecret", "botAppId", "authorization", "apiKey"}
    assert not forbidden.intersection(items["ACC-A"])


@pytest.mark.asyncio
async def test_account_with_another_active_installation_remains_connected(async_client):
    await create_mapping(async_client)
    await async_client.post("/api/teams/installations", json=INSTALLATION)
    await async_client.post(
        "/api/teams/installations",
        json={**INSTALLATION, "teamId": "team-2", "conversationId": "conversation-2"},
    )
    await async_client.post(
        "/api/teams/installations/disconnect",
        json={"tenantId": "tenant-1", "teamId": "team-1"},
    )
    status = (await async_client.get("/api/teams/integration/ACC-001")).json()
    assert status["connected"] is True
    overview = (await async_client.get("/api/teams/integrations")).json()
    assert overview[0]["activeInstallations"] == 1


@pytest.mark.asyncio
async def test_route_assignment_is_normalized_listed_and_account_scoped(async_client):
    await create_mapping(async_client)
    installation = (await async_client.post(
        "/api/teams/installations", json=INSTALLATION
    )).json()["installation"]
    response = await async_client.patch(
        f"/api/teams/installations/ACC-001/{installation['installationId']}/route",
        json={"routeKey": " Risk Alerts "},
    )
    assert response.status_code == 200
    assert response.json()["routeKey"] == "risk-alerts"
    listed = (await async_client.get("/api/teams/installations/ACC-001")).json()
    assert listed[0]["routeKey"] == "risk-alerts"
    assert {"teamName", "channelName", "connectedByName", "enabled"} <= set(listed[0])

    denied = await async_client.patch(
        f"/api/teams/installations/ACC-002/{installation['installationId']}/route",
        json={"routeKey": "finance"},
    )
    assert denied.status_code == 404


@pytest.mark.asyncio
async def test_active_route_unique_per_account_but_shared_across_accounts(async_client):
    await create_mapping(async_client, "ACC-001", "tenant-1")
    await create_mapping(async_client, "ACC-002", "tenant-2")

    async def install(account_id, tenant_id, team_id):
        body = (await async_client.post("/api/teams/installations", json={
            **INSTALLATION, "tenantId": tenant_id, "teamId": team_id,
            "conversationId": f"conversation-{team_id}",
        })).json()["installation"]
        return await async_client.patch(
            f"/api/teams/installations/{account_id}/{body['installationId']}/route",
            json={"routeKey": "finance"},
        )

    assert (await install("ACC-001", "tenant-1", "team-a1")).status_code == 200
    duplicate = await install("ACC-001", "tenant-1", "team-a2")
    assert duplicate.status_code == 409
    assert (await install("ACC-002", "tenant-2", "team-b1")).status_code == 200

    await async_client.post(
        "/api/teams/installations/disconnect",
        json={"tenantId": "tenant-1", "teamId": "team-a1"},
    )
    historical = await async_client.patch(
        f"/api/teams/installations/ACC-001/{(await mongo_manager.database.teams_installations.find_one({'teamId': 'team-a2'}))['_id']}/route",
        json={"routeKey": "finance"},
    )
    assert historical.status_code == 200


@pytest.mark.asyncio
async def test_browser_safe_installation_summaries_are_account_scoped(async_client):
    await create_mapping(async_client, "ACC-001", "tenant-1")
    await create_mapping(async_client, "ACC-002", "tenant-2")
    await async_client.post("/api/teams/installations", json={
        **INSTALLATION, "teamName": "Client A", "channelName": "Sales",
        "channelId": "sales-channel",
    })
    await async_client.post("/api/teams/installations", json={
        **INSTALLATION, "tenantId": "tenant-2", "teamId": "team-b",
        "conversationId": "conversation-b", "teamName": "Client B",
        "channelName": "Finance", "channelId": "finance-channel",
    })
    await async_client.post(
        "/api/teams/installations/disconnect",
        json={"tenantId": "tenant-1", "teamId": "team-1"},
    )

    account_a = (await async_client.get(
        "/api/teams/installation-summaries/ACC-001"
    )).json()
    account_b = (await async_client.get(
        "/api/teams/installation-summaries/ACC-002"
    )).json()
    assert len(account_a) == len(account_b) == 1
    assert account_a[0]["channelName"] == "Sales"
    assert account_a[0]["connected"] is False
    assert account_b[0]["channelName"] == "Finance"
    assert account_b[0]["connected"] is True
    assert set(account_a[0]) == {
        "installationId", "teamName", "channelName", "connected", "enabled",
        "connectedAt", "disconnectedAt",
    }
    forbidden = {
        "serviceUrl", "conversationId", "channelId", "botAppId",
        "connectedById", "connectedByAadObjectId", "tenantId", "accountId",
    }
    assert not forbidden.intersection(account_a[0])
