# Codebase structure

```text
backend/
├── app/
│   ├── main.py                 application factory and lifespan
│   ├── config.py               environment settings
│   ├── database.py             Mongo connection and indexes
│   ├── dependencies.py         dependency graph and guards
│   ├── routers/                HTTP API
│   ├── services/               business workflows
│   ├── repositories/           MongoDB access
│   ├── schemas/                Pydantic API contracts
│   ├── models/                 enums and collection constants
│   ├── exceptions/             typed errors and handlers
│   └── utils/                  logging, middleware, normalization helpers
├── scripts/seed.py             sample-data upsert
├── tests/                       async API/component tests
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## Critical files and relationships

| File | Responsibility / important symbols | Used by / dependencies |
|---|---|---|
| `app/main.py` | `create_app`, `lifespan` | Uvicorn; database, middleware, routers |
| `app/database.py` | `connect_to_mongo`, `create_indexes`, `get_database` | lifespan and every repository dependency |
| `app/dependencies.py` | service/repository factories, `get_current_account_id`, key guard | routers |
| `app/routers/risks.py` | CRUD, projections, send orchestration | risk/notification services |
| `app/routers/teams.py` | tenant, installation, channel, legacy destination APIs | four Teams services |
| `app/services/notification_service.py` | complete send-to-Teams/n8n workflow | risk/routing/log/idempotency/n8n components |
| `app/services/teams_installation_service.py` | provisioning, lifecycle, route resolution | installation/mapping/channel repositories |
| `app/services/action_service.py` | tenant-resolved action dispatch | risk service and mapping repository |
| `app/repositories/risk_repository.py` | tenant-scoped risk persistence and mutations | RiskService |
| `app/schemas/risk.py` | strict generic entity/metric/section risk envelope | routes/services |
| `app/exceptions/handlers.py` | consistent `{"detail":...}` responses | entire API |

`risk_normalizer.py` converts legacy vessel/detail/mitigation shapes lazily at read time. `serializers.py` prevents raw Mongo `_id` leakage except where installation/destination APIs intentionally expose opaque string IDs.
