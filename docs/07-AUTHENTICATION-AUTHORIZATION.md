# Authentication and authorization

There is no user login, JWT/session validation, role system, or authenticated identity middleware.

## Current controls

Risk endpoints obtain account context from `accountId` query or `X-Account-Id`. Values must match `ACC-[A-Za-z0-9]+`; conflicting values return 400. This is tenant scoping, not authentication: callers can choose any syntactically valid account.

Selected internal routes depend on `verify_internal_api_key`. When `INTERNAL_API_KEY_ENABLED=true`, they require `X-Internal-API-Key`; comparison is ordinary string inequality. When false, they are public regardless of environment. Protected routes include action execution, installation registration/disconnect/full lists/routes, integration overview, and channel registration/internal list.

Many administrative/sensitive routes are unguarded: tenant mapping reads/upserts, legacy destinations, account discovery, notification logs, integration status and browser-safe summaries. CORS restricts browsers to configured origins but is not an authentication control and does not restrict non-browser clients.

## Tenant isolation

Risk repository filters consistently include accountId. Explicit installation/destination ObjectIds are resolved within account scope and return the same not-found behavior across invalid/cross-account IDs. Actions resolve account from enabled `tenantId`, preventing the caller from directly supplying accountId. These are useful isolation controls once the caller is authenticated, but current account selection remains spoofable.

Production should derive account and roles from verified identity claims, require a strong internal credential or service identity, protect administrative/read-log routes, compare secrets in constant time, and fail startup when the guard is enabled with a blank key.
