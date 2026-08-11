from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

from app.config import get_settings
from app.database import create_indexes, mongo_manager
from app.main import app
from app.services.n8n_service import N8nService


@pytest_asyncio.fixture(autouse=True)
async def mock_mongo() -> AsyncGenerator[None, None]:
    client = AsyncMongoMockClient()
    mongo_manager.client = client
    mongo_manager.database = client[get_settings().mongodb_db_name]
    await create_indexes()
    yield
    mongo_manager.client = None
    mongo_manager.database = None


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        yield client


@pytest.fixture
def sample_risk_payload() -> dict:
    return {
        "riskId": "RSK-OP-0821", "accountId": "ACC-001",
        "title": "Owner funding is short", "severity": "high", "status": "open",
        "summary": "Additional funding is needed.",
        "entity": {"type": "vessel", "id": "V-2417", "name": "MV Ocean Pioneer",
                   "data": {"imo": "1234567"}},
        "metrics": [{"key": "shortfall", "label": "Funding Shortfall", "value": 210000,
                     "status": "critical", "data": {"currency": "USD"}}],
        "details": {"sections": [
            {"type": "facts", "title": "Risk Details", "items": [{"label": "Exposure", "value": "$210,000"}]},
            {"type": "bullets", "title": "Impact", "items": ["Late supplier payments"]},
            {"type": "future_chart", "title": "Forecast", "series": [1, 2, 3]},
        ]},
        "mitigation": {"sections": [{"type": "steps", "title": "Action Plan", "items": [
            {"title": "Request funding", "description": "Contact owner", "owner": "Finance",
             "status": "pending", "data": {"priority": 1}}
        ]}]},
        "metadata": {"source": "rrm"}, "extensions": {"deadline": "2026-08-15"},
    }


@pytest.fixture
def legacy_risk_document() -> dict:
    return {
        "riskId": "RSK-LEGACY", "accountId": "ACC-001", "title": "Legacy risk",
        "severity": "high", "status": "open", "summary": "Old document",
        "vessel": {"id": "V-OLD", "name": "MV Legacy"}, "fundingShortfall": 10,
        "paymentsAtRisk": 20, "deadline": "2026-08-15", "accountRisk": "High",
        "details": {"underlyingExposure": ["Exposure"], "impact": ["Impact"]},
        "mitigationPlan": {"summary": "Act now", "steps": [{"step": 1, "title": "Do it",
            "description": "Now", "owner": "Ops", "status": "pending"}]},
    }


@pytest.fixture
def mock_n8n_success(monkeypatch):
    async def trigger(self, url, payload, event_id):
        return {"status": "received", "eventId": event_id}
    monkeypatch.setattr(N8nService, "trigger_webhook", trigger)


@pytest.fixture
def mock_n8n_failure(monkeypatch):
    from app.services.n8n_service import N8nDeliveryException
    async def trigger(self, url, payload, event_id):
        raise N8nDeliveryException("simulated network failure")
    monkeypatch.setattr(N8nService, "trigger_webhook", trigger)


@pytest.fixture
def sample_destination_payload() -> dict:
    return {"teamId": "19:sample-team-id", "channelId": "19:sample-channel-id",
            "teamName": "Operations", "channelName": "Risk Alerts", "enabled": True}
