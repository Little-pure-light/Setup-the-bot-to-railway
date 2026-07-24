# Memory V2 Fix / Staging Stage

Spec: `Memory_V2_Fix_Staging_Deployment_Test_Agent_Execution_Specification.md`

## Scope

- Fix design gaps (Identity Charter, Night Growth safety, Embedding, Graph, Reflection status)
- Staging verification readiness
- **No** Redis migration, **no** Production full enable of Memory V2

## Key modules

| Area | Path |
|------|------|
| Identity Charter | `backend/modules/identity_engine.py` |
| Night Growth + safety | `backend/modules/night_growth.py`, `night_growth_safety.py` |
| Internal trigger | `POST /internal/night-growth/run` |
| Graph integrity | `graph_manager.integrity_check`, `scripts/check_memory_graph_integrity.py` |
| Retrieval ranking | `backend/modules/retrieval_engine.py` |
| Reflection status | `ChatResponse.reflection_status` |

## Staging env (suggested)

```text
APP_ENV=staging
MEMORY_V2_ENABLED=true
TOKEN_LEDGER_ENABLED=true
NIGHT_GROWTH_ENABLED=false
NIGHT_GROWTH_INTERNAL_TOKEN=<secret>
IDENTITY_UPDATE_MODE=candidate
REFLECTION_INCLUDE_STATUS=true
```

Production: keep `MEMORY_V2_ENABLED=false`.

## Tests

```bash
python -m pytest tests/ -q
python scripts/check_memory_graph_integrity.py --user-id default_user
```

## Night Growth trigger

```bash
curl -X POST "$STAGING_URL/internal/night-growth/run" \
  -H "Authorization: Bearer $NIGHT_GROWTH_INTERNAL_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"staging_test_user","dry_run":true,"force":false}'
```
