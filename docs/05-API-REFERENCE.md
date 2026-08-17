# API reference

All responses include `X-Correlation-ID`. Application errors use `{"detail":"message"}`; validation errors use `{"detail":[...]}`. Default FastAPI `/docs`, `/redoc`, and `/openapi.json` are enabled.

## Summary

| Method | Endpoint | Purpose | Guard/context |
|---|---|---|---|
| GET | `/health` | Application/Mongo status | Public |
| GET | `/api/accounts` | Minimal account selector | Public |
| POST/GET | `/api/risks` | Create/list risks | `accountId` query or `X-Account-Id` |
| GET/PATCH/DELETE | `/api/risks/{riskId}` | Read/update/delete risk | Account context |
| GET | `/api/risks/{riskId}/notification` | Initial-card business projection | Account context |
| GET | `/api/risks/{riskId}/details` | Detail sections | Account context |
| GET | `/api/risks/{riskId}/mitigation-plan` | Mitigation sections | Account context |
| POST | `/api/risks/{riskId}/send-to-teams` | Queue notification through n8n | Account context; optional idempotency |
| POST | `/api/risk-actions/execute` | Execute Teams action | Optional internal key |
| GET | `/api/notification-logs` | Filtered audit logs | Public |
| GET | `/api/notification-logs/{eventId}` | One audit log | Public |
| PUT/GET | `/api/teams/tenant-mappings/{accountId}` | Upsert/get mapping | Public |
| GET | `/api/teams/tenant-mappings/by-tenant/{tenantId}` | Mapping by tenant | Public |
| POST | `/api/teams/installations` | Register/reactivate installation | Optional internal key |
| POST | `/api/teams/installations/disconnect` | Soft-disconnect installation | Optional internal key |
| GET | `/api/teams/integrations` | All integration overview | Optional internal key |
| GET | `/api/teams/integration/{accountId}` | Integration status | Public |
| GET | `/api/teams/installations/{accountId}` | Full installation history | Optional internal key |
| GET | `/api/teams/installation-summaries/{accountId}` | Browser-safe history | Public |
| PATCH | `/api/teams/installations/{accountId}/{installationId}/route` | Assign route | Optional internal key |
| POST | `/api/teams/channel-destinations` | Register/reactivate channel | Optional internal key |
| GET | `/api/teams/channel-destinations/{accountId}` | Browser-safe channels | Public |
| GET | `/api/teams/channel-destinations-internal/{accountId}` | Full channel records | Optional internal key |
| PUT/GET | `/api/teams/destinations/{accountId}` | Legacy one-per-account destination | Public |
| GET | `/api/teams/destinations` | All legacy destinations | Public |

“Optional internal key” means the header is enforced only when `INTERNAL_API_KEY_ENABLED=true`.

## Risk contract

Create requires body fields `riskId`, `accountId`, `title`, `severity`, `entity`; defaults include `status=open`, empty metrics/sections/metadata/extensions, and disabled tracking/empty assignment. The trusted account context overwrites body `accountId`. `entity` requires type/id/name; metrics require key/label/value. Unknown root fields are rejected; dynamic sections allow extra type-specific fields. `notificationRoute` is trimmed, lower-cased, whitespace-to-hyphen normalized, and limited to alphanumerics, hyphens, and underscores.

List filters: `severity`, `status`, `limit` 1–200 (default 50), `skip` ≥0. PATCH supports every mutable risk content field except `riskId`, `accountId`, and timestamps. Delete is a hard delete. Typical errors: 400 missing/conflicting/invalid account, 404 missing risk, 409 duplicate, 422 invalid schema.

Example account context: `X-Account-Id: ACC-001` or `?accountId=ACC-001`; if both are supplied they must match.

Send body is optional: `{"requestedBy":"user@example.com","installationId":"<object-id>","destinationId":"<object-id>"}`. `requestedBy` must contain `@`. Header `Idempotency-Key` caches only successful results per account. Destination precedence is `destinationId`, then `installationId`, then route/sole active installation. Success: `{"success":true,"eventId":"<uuid>","riskId":"RSK-1","message":"Risk notification queued for Microsoft Teams"}`. Routing conflicts return 404/409; n8n failure returns 502.

## Action contract

```json
{"riskId":"RSK-1","tenantId":"microsoft-tenant","actionKey":"view_details","payload":{}}
```

Actions are `view_details`, `mitigation_plan`, `track_risk`, `assign`. Assign requires `payload.assignedTo` and `assignedBy`; tracking reads optional `actorName`/`actorId`. Read actions return `cardType: dynamic_card` and entity/sections; mutation actions return a message. An unknown/disabled tenant is 409; missing risk is 404.

## Teams contracts

Installation registration requires tenant ID, conversation ID, service URL, bot app ID, and optional team/channel/actor metadata. A new tenant is auto-provisioned; a disabled mapping returns 409. Disconnect requires tenant plus team or conversation and never deletes history.

Channel registration requires tenant/team/channel/conversation/service URL. Tenant must already be mapped and enabled. Route assignment accepts `{"routeKey":"operations"}`. Browser-safe summaries deliberately omit tenant, conversation, service URL, and actor IDs; internal variants expose the full response schema.

Tenant mapping upsert body: `{"tenantId":"tenant","clientName":"Example Client","enabled":true}`. Legacy destination body: `{"teamId":"team","channelId":"channel","teamName":"Operations","channelName":"Alerts","enabled":true}`.

## Notification logs and health

Log filters are `riskId`, `status`, `eventType`, `limit` 1–200, and `skip`. Records contain event/risk/account/destination IDs, status, n8n response, error, and creation time. These routes have no account filter. Health always returns `status: ok`; `database` is `connected`, `disconnected`, or null, so HTTP 200 does not guarantee DB health.
