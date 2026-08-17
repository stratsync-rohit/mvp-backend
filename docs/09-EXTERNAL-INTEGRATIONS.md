# External integrations

## MongoDB

Motor connects using `MONGODB_URL`, pings with a five-second server-selection timeout, and uses `MONGODB_DB_NAME`. Startup fails if unreachable. MongoDB 7 runs privately in Compose with persistent `mongo_data` and a ping healthcheck.

## n8n

The active integration is `N8N_NOTIFICATION_WEBHOOK_URL`. `NotificationService` sends the event, account, resolved Teams destination, and latest risk notification projection. `N8nService` adds `X-Correlation-ID` and JSON content type, waits `N8N_TIMEOUT_SECONDS`, accepts any status below 400, and treats non-JSON success as `{}`. There is no retry, signature, internal-key header, queue, or response-schema validation.

```mermaid
sequenceDiagram
  participant UI as Command Center
  participant API as Backend
  participant DB as MongoDB
  participant N as n8n
  participant B as Teams Bot
  UI->>API: POST risk/send-to-teams
  API->>DB: load risk + destination; pending log
  API->>N: notification event
  N->>B: notification command
  B-->>N: delivery response
  N-->>API: 2xx JSON/empty
  API->>DB: mark success
  API-->>UI: eventId
```

`N8N_ACTION_WEBHOOK_URL` is configured but not called by current code; the n8n service comment calls it future use.

## Microsoft Teams / teams-bot

This backend has no Microsoft SDK or direct Teams network call. The separate bot posts tenant/install/channel lifecycle data. The backend stores `serviceUrl` and conversation identifiers for later n8n/bot delivery. Action requests arrive with `tenantId`, which is mapped to account ownership.

### Teams destination lifecycle and n8n delivery contract

The bot detects Team-level app removal from Microsoft Teams `installationUpdate`
activities whose action is `remove`. The trusted disconnect call disables the exact
account + tenant + Team installation and its matching channel destinations. It does
not affect another Team in the tenant.

Microsoft Teams does not provide a reliable real-time event for every channel
deletion. This implementation therefore detects a deleted or inaccessible channel
when the next proactive send returns a definitive normalized result. The bot treats
`conversation_not_found` and `channel_not_found` as permanent deletion signals and
an explicit membership/permission-removal response as permanent access loss.
Timeouts, network/DNS failures, rate limits, Microsoft 5xx responses, token failures,
and unknown errors remain retryable and do not disable the destination. Microsoft
Graph permissions, polling, and scheduled validation are not used.

The deployed n8n notification workflow must pass `teamsDestination.destinationId`
unchanged to the bot, fail the workflow on bot HTTP 4xx/5xx, and return the bot's
safe structured error fields (`success`, `errorCode`, `destinationId`, `retryable`)
to the backend. If n8n converts a failed bot node into HTTP 200 without that body,
the backend cannot classify or disable the destination and will treat the response
as the legacy successful contract.

## Frontend

CORS allows credentials and all methods/headers for origins in `CORS_ORIGINS`. Frontend implementation is outside this repository. Reverse proxy, TLS, service discovery, and network policies are not confirmed.
