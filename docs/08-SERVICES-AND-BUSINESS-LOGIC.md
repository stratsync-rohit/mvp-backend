# Services and business logic

## `RiskService`

Owns account-scoped CRUD, normalized reads, notification/detail/mitigation projections, and tracking/assignment mutations. Create ignores the body’s account in favor of trusted context. PATCH excludes unset/null fields, so fields cannot currently be cleared to null through PATCH. `risk_normalizer.py` adapts legacy documents without a bulk migration.

## `NotificationService`

Orchestrates the main outbound workflow across risk, installation/channel resolution, notification logs, idempotency, and n8n. Explicit channel destination wins over installation; installation wins over risk route/sole active installation. A caller-supplied idempotency key is checked only after the latest risk exists and caches only success.

## `ActionService`

Resolves an enabled Microsoft tenant mapping, validates risk ownership, then uses a handler map. Details/mitigation return isolated dynamic-card data. Track sets enabled/trackedBy/trackedAt; assign validates and stores assignee/assigner/time.

## Teams services

- `TeamsInstallationService` auto-provisions unknown tenants with an atomic account counter, refuses disabled mappings, preserves optional metadata on sparse upsert, soft-disconnects, assigns unique active route keys, and resolves notification destinations.
- `TeamsChannelDestinationService` requires an existing enabled mapping, independently upserts channels, exposes safe/full lists, scopes ObjectId selection, and disables all channel destinations for a disconnected team.
- `TenantMappingService` provides manual upsert/lookups and deduplicated browser account metadata.
- `TeamsDestinationService` manages the older one-destination-per-account collection.

## Supporting services

`N8nService.trigger_webhook` performs one async POST with correlation ID, parses optional JSON, and normalizes network/non-2xx failure. `NotificationLogService` retrieves/list logs and raises a typed 404. Repositories stamp UTC timestamps and translate no domain errors themselves except natural PyMongo exceptions handled by services/global handlers.
