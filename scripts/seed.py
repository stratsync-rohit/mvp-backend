"""
Seed script: inserts one example risk (RSK-OP-0821) and one Teams
destination (ACC-001).

Idempotent: uses upsert-style logic so running this multiple times will
not create duplicates.

Usage:
    python -m scripts.seed
"""
import asyncio
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient

from app.config import get_settings


async def seed() -> None:
    settings = get_settings()
    client = AsyncIOMotorClient(settings.mongodb_url)
    db = client[settings.mongodb_db_name]

    now = datetime.now(timezone.utc)

    risk_doc = {
        "riskId": "RSK-OP-0821",
        "title": "Owner funding is short",
        "accountId": "ACC-001",
        "severity": "high",
        "summary": "The owner needs to send US$210,000 more by 15 August 2026.",
        "status": "open",
        "entity": {"type": "vessel", "id": "V-OP-2417", "name": "MV Ocean Pioneer", "data": {}},
        "metrics": [
            {"key": "funding_shortfall", "label": "Funding Shortfall", "value": 210000,
             "status": "critical", "data": {"currency": "USD"}},
            {"key": "payments_at_risk", "label": "Payments at Risk", "value": 210000,
             "status": "high", "data": {"currency": "USD"}},
        ],
        "details": {
            "sections": [{"type": "bullets", "title": "Underlying Exposure", "items": [
                "Cash in hand plus expected owner funding is less than required.",
                "Purchase orders and supplier invoices must be paid.",
                "Crew wages cannot be delayed.",
                "No operational cash buffer is left.",
            ]}, {"type": "bullets", "title": "Impact", "items": [
                "Suppliers and crew may be paid late.",
                "Critical supplies or maintenance may be delayed.",
                "Owner relationship may be impacted.",
            ]}],
        },
        "mitigation": {"sections": [
            {"type": "text", "title": "Summary", "content": "Secure additional funding and prioritise critical payments."},
            {"type": "steps", "title": "Action Plan", "items": [
                {
                    "title": "Check the 30-day cash need",
                    "description": "Calculate all critical cash requirements.",
                    "owner": "Fleet Finance Manager",
                    "status": "pending",
                },
                {
                    "title": "Prepare a US$250,000 funding request",
                    "description": "Prepare and validate the owner funding request.",
                    "owner": "Fleet Finance Manager",
                    "status": "pending",
                },
                {
                    "title": "Speak to the owner and agree a deadline",
                    "description": "Confirm funding timeline with the owner.",
                    "owner": "Vessel Manager",
                    "status": "pending",
                },
                {
                    "title": "Prioritise critical payments",
                    "description": "Pay crew, statutory and critical suppliers first.",
                    "owner": "Fleet Director",
                    "status": "pending",
                },
            ]}],
        },
        "metadata": {},
        "extensions": {"deadline": "2026-08-15"},
        "tracking": {"enabled": False, "trackedBy": None, "trackedAt": None},
        "assignment": {"assignedTo": None, "assignedBy": None, "assignedAt": None},
        "updatedAt": now,
    }

    await db.risks.update_one(
        {"riskId": risk_doc["riskId"]},
        {"$set": risk_doc, "$setOnInsert": {"createdAt": now}},
        upsert=True,
    )
    print(f"Seeded risk: {risk_doc['riskId']}")

    destination_doc = {
        "accountId": "ACC-001",
        "teamId": "19:sample-team-id",
        "channelId": "19:sample-channel-id",
        "teamName": "Operations",
        "channelName": "Risk Alerts",
        "enabled": True,
        "updatedAt": now,
    }

    await db.teams_destinations.update_one(
        {"accountId": destination_doc["accountId"]},
        {"$set": destination_doc, "$setOnInsert": {"createdAt": now}},
        upsert=True,
    )
    print(f"Seeded Teams destination for accountId: {destination_doc['accountId']}")

    # Ensure indexes exist even if seed is run before the app has started once.
    await db.risks.create_index("riskId", unique=True)
    await db.risks.create_index("accountId")
    await db.risks.create_index("severity")
    await db.risks.create_index("status")
    await db.risks.create_index("createdAt")
    await db.teams_destinations.create_index("accountId", unique=True)
    await db.notification_logs.create_index("riskId")
    await db.notification_logs.create_index("eventId", unique=True)

    client.close()
    print("Seeding complete.")


if __name__ == "__main__":
    asyncio.run(seed())
