# Developer handover

## Understand first

The backend owns business data and routing; n8n orchestrates notification delivery; teams-bot renders/sends cards. Preserve this boundary. Then understand account scoping, Microsoft tenant mappings, the three Teams destination representations, and the send workflow.

Start with `main.py`, `database.py`, `dependencies.py`, `routers/risks.py`, `services/notification_service.py`, `services/teams_installation_service.py`, and the risk/Teams schemas. Inspect repositories before changing indexes or tenancy.

## Common changes

### Add an API

Add request/response schemas, a thin router operation, service rule, repository operation when persistence is needed, dependency factory, typed errors, and async tests. Include the router in `main.py` and update the API reference.

### Add or change a risk field

Update create/update/response/projection schemas, legacy normalization if needed, service projections, repository mutations/indexes, seed data, tests, frontend/n8n/bot contracts, and database migration/backfill plan. Extra root fields are forbidden.

### Add an action

Extend `ActionKey`, action request/response expectations, `ActionService._handlers`, risk mutation/projection, tests, and teams-bot/n8n card/action contracts.

### Change Teams routing

Decide whether the change concerns app installation, independently selectable channel destination, route key, or legacy destination. Update repository unique indexes and cross-account negative tests together. Never trust an ObjectId without account scope.

### Add an integration

Create a focused async client service, configure validated credentials/timeouts, normalize safe errors, pass correlation IDs, add retries/idempotency appropriate to side effects, and mock plus stage-test the contract.

## Operational handover

Required access: MongoDB, n8n, deployment runtime, logs, teams-bot configuration, and frontend contract. Before release install requirements, run tests, start Mongo-backed application, check indexes/health, exercise CRUD, installation, send, action and disconnect in staging, and verify failed/success audit logs. Deployment/rollback, backups, monitoring and production identity procedures are not confirmed in this repository and must be supplied by the platform owner.
