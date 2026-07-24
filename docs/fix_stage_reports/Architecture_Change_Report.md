# Architecture Change Report — Memory V2 Fix Stage

Date: 2026-07-24  
Base HEAD (pre-commit): `997ddb7653cbf69234e471f884fee6435a55dd1c`  
Status: local changes complete; **not yet committed/pushed**

## Intent

Harden Memory V2 for Staging verification without Redis migration or Production full enable.

## Changes

```text
IdentityEngine → Identity Charter (versioned FS store + candidates)
NightGrowth → safety wrapper (lock / idempotency / execution records)
POST /internal/night-growth/run → token-protected trigger
MemoryManager typed save → embedding_status pending|ready|failed
RetrievalEngine → multi-factor rank + fallback source
GraphManager → created_at/created_by/metadata + integrity_check + archive edges
ChatResponse → reflection_status when include_reflection=true
```

## Non-goals (honored)

- No Redis platform migration
- No Supabase schema big-bang migration
- No Fine-tune / large UI / full chat_router rewrite
- No Production `MEMORY_V2_ENABLED=true` by default

## Data stores (still local-friendly)

| Data | Location |
|------|----------|
| Identity Charter | `data/identity/{user}/` |
| Night Growth exec | `data/night_growth/{user}/` |
| Graph | `data/memory_graph.json` (+ optional Redis key) |
| Token ledger | `data/token_ledger.jsonl` |
