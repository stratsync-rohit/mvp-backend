"""
Shared pytest fixtures.

We use `mongomock-motor` to provide an in-memory Motor-compatible MongoDB
so tests don't require a real MongoDB instance. The n8n service is
monkeypatched so tests never make real network calls.
"""
import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

from app.config import get_settings
from app.database import mongo_manager, create_indexes
from app.main import app
from app.services.n8n_service import N8nService


@pytest_asyncio.fixture(autouse=True)
async def mock_mongo() -> AsyncGenerator[None, None]:
    """Replace the real Mongo client/database with an in-memory mock for every test."""
    settings = get_settings()
    client = AsyncMongoMockClient()
    mongo_manager.client = client
    mongo_manager.database = client[settings.mongodb_db_name]

    await create_indexes()

    yield

    mongo_manager.client = None
    mongo_manager.database = None


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.fixture
def sample_risk_payload() -> dict:
    return {
        "riskId": "RSK-OP-0821",
        "title": "Owner funding is short",
        "vessel": {"id": "V-OP-2417", "name": "MV Ocean Pioneer"},
        "accountId": "ACC-001",
        "severity": "high",
        "summary": "The owner needs to send US$210,000 more by 15 August 2026.",
        "fundingShortfall": 210000,
        "paymentsAtRisk": 210000,
        "deadline": "2026-08-15",
        "accountRisk": "High",
        "status": "open",
        "details": {
            "underlyingExposure": ["Cash in hand plus expected owner funding is less than required."],
            "impact": ["Suppliers and crew may be paid late."],
        },
        "mitigationPlan": {
            "summary": "Secure additional funding and prioritise critical payments.",
            "steps": [
                {
                    "step": 1,
                    "title": "Check the 30-day cash need",
                    "description": "Calculate all critical cash requirements.",
                    "owner": "Fleet Finance Manager",
                    "status": "pending",
                }
            ],
        },
    }


@pytest.fixture
def sample_destination_payload() -> dict:
    return {
        "teamId": "19:sample-team-id",
        "channelId": "19:sample-channel-id",
        "teamName": "Operations",
        "channelName": "Risk Alerts",
        "enabled": True,
    }


@pytest.fixture
def mock_n8n_success(monkeypatch):
    """Patch N8nService.trigger_webhook to succeed without a real HTTP call."""

    async def fake_trigger_webhook(self, url, payload, event_id):
        return {"status": "received", "eventId": event_id}

    monkeypatch.setattr(N8nService, "trigger_webhook", fake_trigger_webhook)


@pytest.fixture
def mock_n8n_failure(monkeypatch):
    """Patch N8nService.trigger_webhook to simulate an n8n delivery failure."""
    from app.services.n8n_service import N8nDeliveryException

    async def fake_trigger_webhook(self, url, payload, event_id):
        raise N8nDeliveryException("simulated network failure")

    monkeypatch.setattr(N8nService, "trigger_webhook", fake_trigger_webhook)
