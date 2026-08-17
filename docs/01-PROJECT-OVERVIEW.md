# Project overview

## Product purpose

The backend is the source of truth and orchestration API for the Microsoft Teams Risk Notification System. The Command Center uses it to manage risks and choose Teams destinations. The teams-bot registers Microsoft installation context and submits user actions. The backend resolves tenant/account ownership, updates risk state, and asks n8n to orchestrate notifications.

## Responsibilities

- Account-scoped risk CRUD, filters, and business-data projections.
- Initial notification orchestration with durable audit log and optional idempotency.
- Risk action execution: view details, mitigation plan, track, and assign.
- Microsoft tenant mapping and automatic `ACC-NNN` provisioning.
- Teams installation, route, channel-destination, legacy destination, and disconnect management.
- Browser-safe account/integration summaries and notification-log reads.
- MongoDB connection lifecycle and index enforcement.

## Actors

| Actor | Interaction |
|---|---|
| Command Center frontend | Risk APIs, account selector, Teams status/destinations, send command |
| teams-bot | Installation/channel registration, disconnect, action execution through n8n/direct flow |
| n8n | Receives initial notification jobs and coordinates bot delivery |
| MongoDB | Durable risk, routing, log, and idempotency state |
| Operator | Configures tenant mappings, integrations, environment, and deployment |

The backend does not call Microsoft Teams or generate Adaptive Card JSON. No background worker or scheduler is implemented.

## Technology stack

FastAPI/Uvicorn provide HTTP/OpenAPI; Pydantic validates strict envelopes; Motor/PyMongo implement async MongoDB access and indexes; httpx calls n8n; standard logging produces structured stdout; pytest, pytest-asyncio, mongomock-motor, and httpx test the application; Docker Compose runs MongoDB 7 and the API.
