# Risk Notification Backend

Backend service for the **Microsoft Teams Risk Notification System**, built for the Command
Center web application. This service stores risk data, serves it to the frontend, triggers n8n
workflows to deliver Microsoft Teams Adaptive Card notifications, and processes action requests
that come back from the Teams bot when a user clicks a card button.

> **This backend does NOT talk to Microsoft Teams directly and does NOT generate Adaptive Card
> JSON.** It returns clean business data. The Teams Bot (a separate service) is responsible for
> rendering and sending Adaptive Cards. n8n is the orchestration layer in between.

---

## 1. What this backend does

1. Stores risk data in MongoDB (single source of truth).
2. Serves risk data to the Command Center frontend.
3. Handles "Send to Teams" requests from the frontend (by `riskId` only).
4. Triggers n8n workflows via webhook to deliver notifications to Microsoft Teams.
5. Serves notification / view-details / mitigation-plan business data.
6. Processes action requests coming back from the Teams bot / n8n (button clicks).
7. Stores Teams destination mappings (`accountId` → team/channel).
8. Stores notification and action logs for auditing.
9. Maps each Microsoft tenant to the correct StratSync account for shared-bot installs.

---

## 2. Architecture

```
Frontend
    ↓ (riskId only)
FastAPI Backend
    ↓
MongoDB  (source of truth)
    ↓
n8n  (orchestration layer)
    ↓
Teams Bot  (renders Adaptive Cards)
    ↓
Microsoft Teams Channel
```

**Reverse action flow** (Teams button click → backend):

```
Microsoft Teams
    ↓
Teams Bot
    ↓
n8n or directly Backend
    ↓
POST /api/risk-actions/execute
    ↓
MongoDB
    ↓
Backend response (business data)
    ↓
Teams Bot renders a NEW Adaptive Card
    ↓
Microsoft Teams Channel
```

Internally, every request flows through layered separation of concerns:

```
Router  →  Service  →  Repository  →  MongoDB
```

Routers contain **no** database logic. Services hold business rules. Repositories are the only
code that talks to Motor/PyMongo.

Key design rules enforced throughout the codebase:

- `riskId` is the single source of truth / main identifier.
- The frontend never sends the full risk object for "Send to Teams" — only `riskId`.
- The backend always re-fetches the latest risk from MongoDB before building any payload.
- Adaptive Card JSON is never generated or stored here.
- `accountId` → Teams destination mapping is used to resolve where a notification goes.

---

## 3. Folder structure

```
backend/
├── app/
│   ├── main.py                  FastAPI app, lifespan, middleware, router registration
│   ├── config.py                Pydantic Settings (env-driven configuration)
│   ├── database.py               MongoDB connection lifecycle + index creation
│   ├── dependencies.py           DI wiring: Router → Service → Repository
│   │
│   ├── models/                   Domain enums/constants (Severity, ActionKey, EventType, ...)
│   ├── schemas/                  Pydantic v2 request/response models
│   ├── repositories/              MongoDB access (the ONLY layer using Motor/PyMongo)
│   ├── services/                  Business logic / orchestration
│   ├── routers/                   FastAPI route definitions (thin, no DB logic)
│   ├── exceptions/                Custom exceptions + centralized error handlers
│   └── utils/                     Logging, correlation-ID middleware, serializers
│
├── tests/                        pytest test suite (mocked MongoDB + mocked n8n)
├── scripts/seed.py               Idempotent MongoDB seed script
│
├── .env.example
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## 4. Environment variables

Copy `.env.example` to `.env` and adjust as needed.

| Variable                        | Description                                              | Default                                                    |
|----------------------------------|------------------------------------------------------------|--------------------------------------------------------------|
| `APP_NAME`                      | Application name shown in Swagger                          | `Risk Notification Backend`                                   |
| `APP_ENV`                       | `development` or `production`                               | `development`                                                 |
| `HOST` / `PORT`                 | Bind address for uvicorn                                    | `0.0.0.0` / `8000`                                             |
| `MONGODB_URL`                   | MongoDB connection string                                    | `mongodb://mongo:27017`                                        |
| `MONGODB_DB_NAME`                | Database name                                               | `notifications_db`                                              |
| `N8N_NOTIFICATION_WEBHOOK_URL`   | n8n webhook for initial Teams notifications                  | *(must be set)*                                                 |
| `N8N_ACTION_WEBHOOK_URL`         | n8n webhook reserved for future action-result push          | *(must be set)*                                                 |
| `N8N_TIMEOUT_SECONDS`           | HTTP timeout when calling n8n                                | `15`                                                             |
| `LOG_LEVEL`                     | Logging level                                                | `INFO`                                                           |
| `CORS_ORIGINS`                  | Comma-separated list of allowed origins                      | `http://localhost:3000`                                          |
| `INTERNAL_API_KEY`              | Shared secret for internal endpoints                          | *(empty)*                                                        |
| `INTERNAL_API_KEY_ENABLED`      | Enables the `X-Internal-API-Key` guard on internal endpoints  | `false`                                                          |

No secrets are committed. `.env` is git-ignored.

---

## 5. How to run locally (without Docker)

Requires Python 3.12 and a running MongoDB instance (local or remote).

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env -> set MONGODB_URL=mongodb://localhost:27017 if running Mongo locally

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The app will refuse to start (and log a clear error) if it cannot reach MongoDB — this is
intentional per the design requirements.

---

## 6. How to run with Docker Compose

```bash
cd backend
docker compose up --build
```

This starts:
- `mongo` — MongoDB 7, with a persistent volume (`mongo_data`) and a healthcheck. Port `27017`
  is exposed for local convenience/inspection only — **do not expose Mongo publicly in
  production**; in production it should only be reachable on the internal Docker network.
- `backend` — the FastAPI service, waiting for Mongo's healthcheck before starting, exposed on
  port `8000`.

Override `N8N_NOTIFICATION_WEBHOOK_URL` / `N8N_ACTION_WEBHOOK_URL` via a `.env` file in the same
directory as `docker-compose.yml` (Compose automatically loads it), e.g.:

```
N8N_NOTIFICATION_WEBHOOK_URL=https://your-n8n-instance/webhook/teams-notification
N8N_ACTION_WEBHOOK_URL=https://your-n8n-instance/webhook/teams-action
```

---

## 7. How to seed sample data

Idempotent — safe to run multiple times, it will upsert rather than duplicate.

```bash
# Local (venv active, MongoDB reachable via MONGODB_URL in .env)
python -m scripts.seed

# Inside Docker Compose
docker compose exec backend python -m scripts.seed
```

This inserts:
- Risk `RSK-OP-0821` (MV Ocean Pioneer / owner funding shortfall example)
- Teams destination for `ACC-001` (team "Operations" / channel "Risk Alerts")

---

## 8. How to test the APIs using Swagger

With the app running, open:

- Swagger UI: **http://localhost:8000/docs**
- OpenAPI schema: **http://localhost:8000/openapi.json**

All endpoints are tagged and documented with descriptions and response models.

---

## 9. Example curl commands

### Health check
```bash
curl http://localhost:8000/health
```

### Create a risk
```bash
curl -X POST http://localhost:8000/api/risks \
  -H "Content-Type: application/json" \
  -d @scripts/example_risk.json
```
(or use the seed script instead)

### List risks
```bash
curl "http://localhost:8000/api/risks?severity=high&status=open"
```

### Get a risk
```bash
curl http://localhost:8000/api/risks/RSK-OP-0821
```

### Configure a Teams destination
```bash
curl -X PUT http://localhost:8000/api/teams/destinations/ACC-001 \
  -H "Content-Type: application/json" \
  -d '{
    "teamId": "19:xxxxxxxx",
    "channelId": "19:yyyyyyyy",
    "teamName": "Operations",
    "channelName": "Risk Alerts",
    "enabled": true
  }'
```

### Onboard a client for the shared Teams bot

No manual mapping is needed. The bot sends the Microsoft `tenantId` (never an
`accountId`) to `POST /api/teams/installations`. The backend reuses an enabled
mapping when one exists; otherwise it atomically allocates the next `ACC-NNN`,
creates the tenant mapping, and continues the normal installation upsert.

The counter is reconciled against the maximum numeric suffix already present, so
existing mappings are unchanged and gaps are safe. `teamName` is used only as a
provisional `clientName`; when it is absent, `accountId` is the display-name
fallback. A canonical name can still be applied later through the mapping API.
A disabled mapping is never replaced or automatically re-enabled: registration
returns HTTP 409 and retains its historical account ownership.

Confirm an installed client's result using the allocated account ID:

```bash
curl http://localhost:8000/api/teams/integration/ACC-002
```

### Teams installation lifecycle

Registration always makes the matching installation active, clears
`disconnectedAt`, and refreshes its Teams routing fields. When Teams reports that
an app was removed, the bot sends the tenant plus the installation identity (never
an `accountId` supplied by the bot):

```bash
curl -X POST http://localhost:8000/api/teams/installations/disconnect \
  -H "Content-Type: application/json" \
  -H "X-Internal-API-Key: $INTERNAL_API_KEY" \
  -d '{
    "tenantId": "CLIENT_TENANT_ID",
    "teamId": "MICROSOFT_TEAM_ID",
    "conversationId": "OPTIONAL_CONVERSATION_ID"
  }'
```

At least one of `teamId` or `conversationId` is required. The backend resolves the
enabled tenant mapping to its canonical `accountId` and only soft-disconnects the
active installation matching that account, tenant, and supplied identity. A missing
active match returns a controlled success with `disconnected: false`; records are
never deleted.

The internal multi-client summary is available at:

```bash
curl http://localhost:8000/api/teams/integrations \
  -H "X-Internal-API-Key: $INTERNAL_API_KEY"
```

It uses `tenant_mappings.clientName` as `accountName` (falling back to `accountId`)
and exposes optional `channelName` and `connectedByName` display metadata from
the latest active installation. `connectedByName` is the actor supplied on the
Teams connection lifecycle activity, not a claim that the user is an account
owner or Teams administrator. Sparse re-registration events retain previously
captured non-null optional metadata and the overview omits service URLs and
credentials. Both endpoints reuse the existing optional
internal API-key guard. In deployed environments, set a strong `INTERNAL_API_KEY`
and `INTERNAL_API_KEY_ENABLED=true`; when disabled, these routes are unauthenticated.

#### Repair a confirmed stale installation

An uninstall event that happened before lifecycle handling was deployed cannot be
replayed. After confirming the exact stale tenant and Teams identity, issue the
disconnect call above once. Supplying both known `teamId` and `conversationId` gives
the narrowest match. This changes only that active document to `enabled: false` and
sets `disconnectedAt`/`updatedAt`; it does not disable other installations or delete
history.

### Send to Teams
```bash
curl -X POST http://localhost:8000/api/risks/RSK-OP-0821/send-to-teams \
  -H "Content-Type: application/json" \
  -d '{"installationId": "MONGODB_OBJECT_ID", "requestedBy": "user@example.com"}'
```

The browser obtains safe installation identifiers from
`GET /api/teams/installation-summaries/{accountId}`. An explicit
`installationId` always takes precedence over `risk.notificationRoute` and is
resolved together with the current account. Route-based/legacy resolution is
used only when `installationId` is omitted.

Optional idempotency protection:
```bash
curl -X POST http://localhost:8000/api/risks/RSK-OP-0821/send-to-teams \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: 6f1b6a2e-64a1-4e2b-9e10-3a1e2b7c9999" \
  -d '{}'
```

### View Details action (called by bot/n8n)
```bash
curl -X POST http://localhost:8000/api/risk-actions/execute \
  -H "Content-Type: application/json" \
  -d '{"riskId": "RSK-OP-0821", "actionKey": "view_details"}'
```

### Mitigation Plan action
```bash
curl -X POST http://localhost:8000/api/risk-actions/execute \
  -H "Content-Type: application/json" \
  -d '{"riskId": "RSK-OP-0821", "actionKey": "mitigation_plan"}'
```

### Track This Problem action
```bash
curl -X POST http://localhost:8000/api/risk-actions/execute \
  -H "Content-Type: application/json" \
  -d '{"riskId": "RSK-OP-0821", "actionKey": "track_risk", "payload": {"actorName": "manager@example.com"}}'
```

### Assign To action
```bash
curl -X POST http://localhost:8000/api/risk-actions/execute \
  -H "Content-Type: application/json" \
  -d '{"riskId": "RSK-OP-0821", "actionKey": "assign", "payload": {"assignedTo": "john@example.com", "assignedBy": "manager@example.com"}}'
```

### Notification logs
```bash
curl "http://localhost:8000/api/notification-logs?riskId=RSK-OP-0821"
```

If `INTERNAL_API_KEY_ENABLED=true`, add `-H "X-Internal-API-Key: <your-key>"` to the
`risk-actions/execute` call.

---

## 10. Send to Teams flow (detail)

`POST /api/risks/{riskId}/send-to-teams`

1. Validate the risk exists (404 if not).
2. Load the **latest** risk document from MongoDB.
3. Use the trusted current account context.
4. If supplied, resolve the exact active installation by current account plus
   `installationId`; otherwise use the existing route/legacy resolver.
5. Reject an inactive selected installation with 409 and never fall back.
6. Build the clean initial-notification payload (no Adaptive Card JSON).
7. Generate a UUID `eventId` used as the correlation ID.
8. Insert a `pending` notification log.
9. POST to `N8N_NOTIFICATION_WEBHOOK_URL` with header `X-Correlation-ID: <eventId>`.
10. On success → update the log to `success` and store n8n's response.
    On failure (network error or non-2xx) → update the log to `failed` and return **502** with a
    generic message (`Unable to queue Microsoft Teams notification`) — n8n's internal error
    details are never exposed to the frontend.
11. Return `{ success, eventId, riskId, message }` to the frontend.

An optional `Idempotency-Key` header protects against accidental duplicate rapid-fire requests:
if the same key was already processed successfully, the cached result is returned instead of
re-triggering n8n.

---

## 11. Teams button action flow (detail)

`POST /api/risk-actions/execute`

Internally uses a handler-mapping pattern (no large if/elif chains):

```python
handlers = {
    ActionKey.VIEW_DETAILS: handle_view_details,
    ActionKey.MITIGATION_PLAN: handle_mitigation_plan,
    ActionKey.TRACK_RISK: handle_track_risk,
    ActionKey.ASSIGN: handle_assign,
}
```

| actionKey          | Behavior                                                                                  |
|---------------------|----------------------------------------------------------------------------------------------|
| `view_details`      | Returns `{ riskId, actionKey, cardType: "risk_details", data }` — no DB mutation.               |
| `mitigation_plan`   | Returns `{ riskId, actionKey, cardType: "mitigation_plan", data }` — no DB mutation.             |
| `track_risk`        | Sets `tracking.enabled = true`, `tracking.trackedAt = now`. Returns a success envelope.          |
| `assign`            | Requires `payload.assignedTo` / `payload.assignedBy`. Updates `assignment.*`. Returns success.   |

For `view_details` and `mitigation_plan` the backend **only returns business data** — the Teams
bot is responsible for turning that into a new Adaptive Card and sending it.

---

## 12. MongoDB collections

### `risks`
Unique index on `riskId`. Additional indexes on `accountId`, `severity`, `status`, `createdAt`.
Holds the full risk document (title, vessel, severity, funding figures, details, mitigation
plan, tracking, assignment).

### `teams_destinations`
Unique index on `accountId`. Currently a strict one-to-one `accountId → team/channel` mapping;
the repository/service layer is written so this can be extended to multiple destinations per
account later without breaking the public API shape.

### `notification_logs`
Indexes on `riskId`, unique `eventId`, `status`, `eventType`, `createdAt`. One row per
notification/action event, with `pending → success|failed` status transitions and the raw
(but safe) n8n response stored for audit purposes.

### `idempotency_keys`
Internal collection backing the `Idempotency-Key` header support on Send-to-Teams. Compound
unique index on `(key, scope)`.

---

## 13. n8n integration contract

Two webhook URLs, both required, injected via environment variables — never hardcoded:

- `N8N_NOTIFICATION_WEBHOOK_URL` — called by `POST /api/risks/{riskId}/send-to-teams`.
- `N8N_ACTION_WEBHOOK_URL` — reserved for future use (pushing action results asynchronously);
  currently `POST /api/risk-actions/execute` returns its result synchronously and directly.

All outbound calls go through a single reusable coroutine:

```python
async def trigger_webhook(url: str, payload: dict, event_id: str) -> dict:
    ...
```

- Uses `httpx.AsyncClient` with a configurable timeout (`N8N_TIMEOUT_SECONDS`).
- Sends header `X-Correlation-ID: <eventId>`.
- Raises an internal `N8nDeliveryException` on network errors or non-2xx responses, which the
  calling service translates into a safe `502 { "detail": "Unable to queue Microsoft Teams
  notification" }` — the raw n8n error/stack trace is never returned to the client, only logged
  server-side.

Notification payload shape sent to n8n:

```json
{
  "eventId": "uuid",
  "eventType": "initial_notification",
  "riskId": "RSK-OP-0821",
  "destination": { "teamId": "19:xxxx", "channelId": "19:yyyy" },
  "notification": {
    "riskId": "RSK-OP-0821",
    "title": "Owner funding is short",
    "vessel": { "id": "V-OP-2417", "name": "MV Ocean Pioneer" },
    "severity": "high",
    "summary": "...",
    "deadline": "2026-08-15",
    "actions": [
      { "key": "view_details", "label": "View Details" },
      { "key": "mitigation_plan", "label": "Mitigation Plan" },
      { "key": "assign", "label": "Assign To" },
      { "key": "track_risk", "label": "Track This Problem" }
    ]
  }
}
```

---

## 14. Production considerations

- **Do not** expose MongoDB port `27017` publicly — only the `backend` service should reach it,
  over the internal Docker/Kubernetes network.
- **CORS**: set `CORS_ORIGINS` to the exact list of trusted frontend origins — never `*` in
  production.
- **Internal API key**: set `INTERNAL_API_KEY_ENABLED=true` and a strong `INTERNAL_API_KEY` in
  production so `POST /api/risk-actions/execute` can only be called by trusted services
  (Teams bot / n8n), not arbitrary clients.
- **Secrets**: `N8N_NOTIFICATION_WEBHOOK_URL`, `N8N_ACTION_WEBHOOK_URL`, and
  `INTERNAL_API_KEY` should be injected via your platform's secret manager, not committed to
  source control.
- **TLS**: terminate TLS in front of this service (load balancer / ingress) in production.
- **Horizontal scaling**: the service is stateless aside from MongoDB, so it can be scaled
  horizontally behind a load balancer. The idempotency-key mechanism is implemented in MongoDB
  precisely so it works correctly across multiple backend replicas.
- **Observability**: structured logs are emitted to stdout (`app.utils.logger`) — ship these to
  your log aggregator of choice. Every request carries an `X-Correlation-ID` that is also used
  as the n8n correlation header and the notification log `eventId`, making it possible to trace
  a request end-to-end.
- **Mongo indexes**: created automatically on startup (`create_indexes()`); safe to re-run.

---

## Final project tree

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── dependencies.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── risk.py
│   │   ├── teams_destination.py
│   │   └── notification_log.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── risk.py
│   │   ├── teams.py
│   │   ├── actions.py
│   │   ├── notification_log.py
│   │   └── common.py
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── risk_repository.py
│   │   ├── teams_destination_repository.py
│   │   ├── notification_log_repository.py
│   │   └── idempotency_repository.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── risk_service.py
│   │   ├── notification_service.py
│   │   ├── teams_destination_service.py
│   │   ├── action_service.py
│   │   ├── notification_log_service.py
│   │   └── n8n_service.py
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── risks.py
│   │   ├── risk_actions.py
│   │   ├── teams.py
│   │   ├── notification_logs.py
│   │   └── health.py
│   ├── exceptions/
│   │   ├── __init__.py
│   │   └── handlers.py
│   └── utils/
│       ├── __init__.py
│       ├── logger.py
│       ├── middleware.py
│       └── serializers.py
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_health.py
│   ├── test_risks.py
│   └── test_actions.py
│
├── scripts/
│   ├── __init__.py
│   └── seed.py
│
├── .env.example
├── .gitignore
├── pytest.ini
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## Commands quick reference

```bash
# Start (Docker Compose)
docker compose up --build

# Start (local venv, MongoDB running separately)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Seed sample data
python -m scripts.seed

# Run tests (21 tests, MongoDB and n8n both mocked - no external dependencies required)
pytest -v
```

Test URLs once running:
- Swagger: http://localhost:8000/docs
- Health: http://localhost:8000/health
- Risks: http://localhost:8000/api/risks
