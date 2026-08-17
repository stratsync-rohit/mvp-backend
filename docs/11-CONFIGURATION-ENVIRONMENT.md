# Configuration and environment

`Settings` in `app/config.py` loads case-insensitive process environment and `.env`, ignores unknown keys, and is cached. Process environment overrides dotenv. Restart or clear the cache after changes.

| Variable | Required | Purpose | Safe example |
|---|---:|---|---|
| `APP_NAME` | No | OpenAPI application name | `Risk Notification Backend` |
| `APP_ENV` | No | Environment label/development helper | `production` |
| `HOST` | No | Documented bind host; app does not start Uvicorn | `0.0.0.0` |
| `PORT` | No | Documented bind port | `8000` |
| `MONGODB_URL` | Yes | Mongo connection | `mongodb://mongo:27017` |
| `MONGODB_DB_NAME` | No | Database name | `notifications_db` |
| `N8N_NOTIFICATION_WEBHOOK_URL` | Send flow | Active notification webhook | `https://n8n.example/webhook/<id>` |
| `N8N_ACTION_WEBHOOK_URL` | No/currently unused | Reserved action webhook | `https://n8n.example/webhook/<id>` |
| `N8N_TIMEOUT_SECONDS` | No | Outbound timeout | `15` |
| `LOG_LEVEL` | No | Root logging level | `INFO` |
| `CORS_ORIGINS` | Browser use | Comma-separated exact origins | `https://app.example` |
| `INTERNAL_API_KEY` | Production | Shared internal secret | `<secret>` |
| `INTERNAL_API_KEY_ENABLED` | Production | Enables selected-route guard | `true` |

`.env.example`, Compose, and source contain the same variable names. Docker image does not copy `.env`; Compose injects values. The `.env.example` contains a concrete public n8n host/path rather than a placeholder; it is not a credential, but deployment-specific endpoints are better supplied externally.

Observed risks: settings provide functional example n8n defaults rather than failing closed; enabling the key guard with an empty key is allowed; `HOST`/`PORT` do not automatically change the hard-coded Docker command; `APP_ENV` does not enforce any production validation.
