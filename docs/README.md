# Risk Notification Backend documentation

This FastAPI service is the persistence and business-orchestration layer for StratSync risk notifications. It stores account-scoped risks and Microsoft Teams routing data in MongoDB, serves the Command Center, sends notification jobs to n8n, and processes Teams-originated risk actions. Adaptive Card rendering and Teams delivery belong to the separate `teams-bot` service.

| Area | Implementation |
|---|---|
| Runtime/API | Python 3.12, FastAPI, Uvicorn |
| Persistence | MongoDB 7, Motor/PyMongo |
| Validation | Pydantic v2 / pydantic-settings |
| Integration | n8n webhook; Teams context received via teams-bot |
| Architecture | Router → Service → Repository → MongoDB |
| Deployment | Docker and Docker Compose |

Quick start: `docker compose up --build`, then open `http://localhost:8000/docs`.

## Recommended reading order

1. [Project Overview](01-PROJECT-OVERVIEW.md)
2. [System Architecture](02-SYSTEM-ARCHITECTURE.md)
3. [Codebase Structure](03-CODEBASE-STRUCTURE.md)
4. [Application Flow](04-APPLICATION-FLOW.md)
5. [API Reference](05-API-REFERENCE.md)
6. [Database Design](06-DATABASE-DESIGN.md)
7. [Authentication and Authorization](07-AUTHENTICATION-AUTHORIZATION.md)
8. [Services and Business Logic](08-SERVICES-AND-BUSINESS-LOGIC.md)
9. [External Integrations](09-EXTERNAL-INTEGRATIONS.md)
10. [Developer Handover](18-DEVELOPER-HANDOVER.md)

Additional guides: [events](10-WEBHOOKS-AND-EVENTS.md), [configuration](11-CONFIGURATION-ENVIRONMENT.md), [local development](12-LOCAL-DEVELOPMENT.md), [deployment](13-DEPLOYMENT-INFRASTRUCTURE.md), [errors/logging](14-ERROR-HANDLING-LOGGING.md), [testing](15-TESTING.md), [security](16-SECURITY.md), [troubleshooting](17-TROUBLESHOOTING.md), and [technical debt](19-TECHNICAL-DEBT-AND-IMPROVEMENTS.md).
