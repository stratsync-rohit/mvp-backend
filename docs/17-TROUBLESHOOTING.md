# Troubleshooting

| Symptom | Verification | Fix / files |
|---|---|---|
| App exits on startup | Mongo ping/index error in stdout | Check `MONGODB_URL`, Mongo health, duplicates; `database.py` |
| Health says `ok` but DB `disconnected` | Inspect `database` field and Mongo logs | Restore Mongo; health intentionally remains HTTP 200 |
| Risk API returns 400 | Missing/conflicting/invalid account context | Send matching `accountId` or `X-Account-Id` (`dependencies.py`) |
| 401 internal route | Guard enabled and key absent/mismatch | Set/send consistent internal key |
| 409 on install | Disabled tenant mapping or route conflict | Inspect mapping and active route ownership |
| Send returns “route required” | Multiple active installs, no risk route/explicit selection | Set normalized `notificationRoute` or pass installation/destination ID |
| Send returns 502 | n8n network/non-2xx | Search event ID; inspect failed notification log and n8n |
| Repeated send re-triggers n8n | Missing/different key or concurrent first calls | Reuse `Idempotency-Key`; improve atomic reservation |
| Seed breaks duplicate IDs across accounts | Inspect `riskId_1` index | Drop obsolete global index only after review; fix `scripts/seed.py` |
| Tests cannot start | `pytest` absent or `app` import failure | Install requirements; run `PYTHONPATH=. pytest -q` |
| Channel disappeared after uninstall | Team disconnect disables all matching channels | Confirm intended Teams lifecycle behavior |
| Legacy risk response fails | Inspect normalization fields/timestamps | Review `risk_normalizer.py` and repository lazy backfill |

Logs are on stdout. Use `X-Correlation-ID`, eventId, riskId, accountId and tenantId for tracing, but note request correlation is not automatically attached to every service log.
