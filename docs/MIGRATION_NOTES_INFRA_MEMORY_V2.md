# Migration Notes — Infrastructure + Memory V2 Phase 2

## Breaking changes

**None** for public HTTP APIs (`/api/chat`, `/v1/*`).

## Optional env

| Variable | Default | Notes |
|----------|---------|-------|
| `MEMORY_V2_ENABLED` | false | Enable V2 façade on chat |
| `TOKEN_LEDGER_ENABLED` | true | Write token_ledger.jsonl |
| `TOKEN_LEDGER_PATH` | data/token_ledger.jsonl | |
| `IDENTITY_STORE_DIR` | data/identity | |
| `MEMORY_GRAPH_FILE` | data/memory_graph.json | |

## Data

- Redis keys: only `conv:{id}:latest` for conversation latest (normalized payload)
- Reflection records gain canonical `reflection` object; legacy fields kept
- Graph edges migrate legacy `source_id` → `source_memory_id` on load
- Identity store is filesystem JSON (no DB migration required)

## SQL optional

```bash
python scripts/migrate_memory_v2.py --print-sql
```

## Rollback

1. `MEMORY_V2_ENABLED=false`
2. Redeploy previous commit if needed
3. Identity/graph JSON files can remain unused
