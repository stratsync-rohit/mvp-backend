# Error handling and logging

`AppError` subclasses centralize expected statuses: 404 missing resources, 409 duplicates/disabled/ambiguous routing/unmapped tenants, 401 internal key, and 502 n8n delivery. The handler returns `{"detail":"..."}`. Validation errors remove Pydantic `ctx` before returning 422. Unexpected exceptions are logged with stack trace and returned as generic 500 without internal details.

Mongo startup errors are converted to `RuntimeError` and stop startup. Duplicate-key handling is explicit for risk creation and installation route conflicts where implemented; other raw database errors reach the generic handler.

## Logging

`StructuredFormatter` writes one-line key/value records to stdout and merges arbitrary `extra` fields. Root level comes from `LOG_LEVEL`; handlers are cleared on configuration to avoid reload duplicates. n8n URLs/payloads are not logged, but identifiers, paths, error types and some messages are.

`CorrelationIdMiddleware` accepts or creates `X-Correlation-ID`, stores it on `request.state`, and returns it. It is passed to n8n as the generated notification event ID, not necessarily the incoming request correlation ID. Most business logs do not automatically include request correlation ID.

No metrics, tracing, audit retention, log redaction schema, alerting, or centralized logging configuration is present. Notification logs provide business delivery audit but action mutations are not written there despite the collection description mentioning action logs.
