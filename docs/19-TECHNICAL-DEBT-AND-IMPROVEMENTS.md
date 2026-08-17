# Technical debt and improvements

No application changes were made for these findings.

## Critical

| Problem | Evidence/location | Impact | Improvement |
|---|---|---|---|
| No real authentication; caller chooses account | `get_current_account_id`; public admin/read routes | Cross-tenant compromise | Verified identities, account claims and RBAC |
| Internal protection defaults disabled | settings/dependency/Compose | Internet-exposed internal mutations if misdeployed | Production startup validation; secure-by-default guard |

## High

| Problem | Evidence/location | Impact | Improvement |
|---|---|---|---|
| Public tenant mapping and legacy destination writes | `routers/teams.py` | Tenant/routing takeover | Admin authorization |
| Public, unscoped notification logs | `routers/notification_logs.py` | Multi-tenant data leakage | Account filters and audit permission |
| Seed recreates obsolete global riskId uniqueness | `scripts/seed.py` vs `database.py` | Multi-tenant inserts fail | Reuse central index setup/remove index creation from seed |
| No durable retry/queue for n8n | `N8nService`/send flow | Transient notification loss | Outbox/worker with retry and stable event idempotency |
| Idempotency check/save is not atomic | repository/service | Concurrent duplicate sends | Atomic reservation/status model |

## Medium

| Problem | Evidence/location | Impact | Improvement |
|---|---|---|---|
| Three overlapping Teams destination models | installations, channel destinations, legacy destinations | Confusing ownership/migration | Define canonical model and deprecate legacy collection/routes |
| Idempotency has no TTL | index/repository | Unbounded growth/stale replay | TTL index and retention policy |
| PATCH excludes null | `RiskService.update_risk` | Optional values cannot be cleared | Preserve explicit null with field-level rules |
| Health returns 200/ok on DB failure | health router | Load balancer may route broken instance | Separate liveness/readiness and non-2xx readiness |
| New httpx client per n8n call | `N8nService` | Connection overhead | Lifespan-managed client |
| Correlation context not propagated through logs | middleware/services | Harder tracing | Context variable/log filter |
| Action events are not audit-logged | action service/log collection intent | Incomplete audit trail | Add action audit records |
| `N8N_ACTION_WEBHOOK_URL`, HOST/PORT unused | config | Configuration confusion | Remove or wire/document lifecycle |

## Low

| Problem | Evidence/location | Impact | Improvement |
|---|---|---|---|
| Mutable `{}` default in notification schema | `NotificationLogResponse` | Style/possible sharing concern | `Field(default_factory=dict)` |
| No database migration tool | startup index mutation/lazy backfill | Risky production upgrades | Versioned migrations and preflight |
| No backend Docker healthcheck/CI | deployment files | Weaker release confidence | Healthcheck and CI test/build/security gates |
| README contains some stale descriptions | comments/routes evolved | Handover drift | Keep concise README linked to versioned docs |
