# Security review

## Existing protections

- Strict Pydantic risk envelopes and bounded pagination.
- Repository-level account filters for risk and selected ObjectId access.
- Tenant-derived account ownership for action/install flows.
- Optional internal API key on selected service routes.
- Configured browser CORS allowlist and correlation IDs.
- Generic 500 responses and centralized validation cleanup.
- Mongo `_id` is hidden except intentional opaque installation/destination IDs.
- Container runs as non-root; Mongo is not host-exposed in Compose.

## Potential risks

| Severity | Finding | Impact |
|---|---|---|
| Critical | Account context is caller-controlled and many admin/read endpoints are public | Cross-tenant data access/mutation |
| Critical configuration | Internal key protection defaults off in all environments | Internal lifecycle/action APIs may be public |
| High | Tenant mapping upsert/read and legacy destinations are unguarded | Ownership/routing takeover |
| High | Notification logs are unscoped and public | Cross-account operational data exposure |
| High | n8n webhook has no authentication/signature and permissive example default | Event spoofing/misdirection risk |
| Medium | Internal key comparison is not constant-time and can be enabled blank | Weak secret control |
| Medium | CORS allows credentials with all methods/headers | Broad browser capability for configured origins |
| Medium | Idempotency records never expire and race protection is last-write-wins | Storage growth; duplicate outbound calls on races |
| Medium | No rate/body limits or explicit API docs restriction | Abuse/reconnaissance |
| Medium | Mongo Compose has no authentication | Network compromise exposes data |

## Recommended improvements

Implement verified user/service authentication and role-based account claims; protect every administrative/log endpoint; fail production startup without strong credentials and valid URLs; sign outbound webhooks; authenticate Mongo and use TLS/network policy; use constant-time secret comparison; add atomic reservation plus TTL for idempotency; restrict docs/CORS; enforce edge rate and body-size limits; add secret/dependency/container scanning and audit retention policy.
