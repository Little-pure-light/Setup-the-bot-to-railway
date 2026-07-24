# Night Growth Safety Report

## Guarantees

1. **Idempotency**: formal `completed` for same `user_id` + UTC day → `skipped_duplicate` unless `force=true`
2. **Lock**: file lock prevents concurrent runs per user
3. **dry_run**: does **not** consume daily idempotency (`completed_dry_run`)
4. **Execution record**: `execution_id`, steps with started_at/completed_at/status/error, saved ids, identity_version_id, graph_edge_ids
5. **Failed runs**: status `failed` → retriable (not treated as day completed)
6. **No multi-replica auto-start**: in-process scheduler not started in `main` lifespan; `NIGHT_GROWTH_ENABLED` default false

## Endpoint

```text
POST /internal/night-growth/run
Authorization: Bearer <NIGHT_GROWTH_INTERNAL_TOKEN>
Body: { "user_id", "conversation_id?", "dry_run", "force" }
```

Anonymous public access forbidden (token required; unconfigured → 503).

## Tests

Idempotency + lock unit tests in `test_memory_v2_fix_stage.py`.
