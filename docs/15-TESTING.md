# Testing

The suite uses pytest, pytest-asyncio (`asyncio_mode=auto`), httpx ASGI clients, and mongomock-motor. `tests/conftest.py` supplies a mock Mongo database, overrides dependencies, and provides reusable risk/legacy documents and mocked n8n outcomes.

| Test module | Main coverage |
|---|---|
| `test_health.py` | Health response |
| `test_accounts.py` | Safe selector and internal overview guard |
| `test_risks.py` | Generic/legacy schemas, CRUD, routes, delivery failures/selections |
| `test_multi_tenant_risks.py` | Account isolation and tenant-resolved actions |
| `test_actions.py` | Four actions and validation/errors |
| `test_teams_installations.py` | Mapping, auto-provision races, lifecycle, routes, summaries |
| `test_teams_channel_destinations.py` | Per-channel upserts, safe fields, isolation, uninstall |

Run after installing requirements:

```bash
PYTHONPATH=. pytest -q
```

No exact coverage percentage is available. Gaps include real Mongo index migration behavior, real n8n contracts, Docker smoke tests, authentication/security tests, CORS, malformed transport/global failures, performance, backup/restore, and production concurrency. mongomock may differ from MongoDB for partial unique indexes, aggregation, and concurrent atomic behavior.

Validation status: the existing `.venv` lacked pytest and system pytest was unavailable, so no pass count could be confirmed during this documentation run. The pre-existing modified `tests/test_teams_channel_destinations.py` was preserved unchanged.
