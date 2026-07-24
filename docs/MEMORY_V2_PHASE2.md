# Memory V2 Phase 2 — Cognitive Upgrade

## New Modules

| Module | Path |
|--------|------|
| Identity Engine | `backend/modules/identity_engine.py` |
| Semantic Builder | `backend/modules/semantic_builder.py` |
| Decision Engine | `backend/modules/decision_engine.py` |
| Scheduler | `backend/modules/scheduler.py` |

## Updated

- `graph_manager.py` — nodes = **memory_id** only; edge has confidence + timestamp
- `retrieval_engine.py` — Intent → Type → **Embedding** → Graph → Rank
- `night_growth.py` — v2 pipeline + `register_scheduler()`

## Flags

```text
MEMORY_V2_ENABLED=false   # default; chat uses V1 path
IDENTITY_STORE_DIR=data/identity
MEMORY_GRAPH_FILE=data/memory_graph.json
TOKEN_LEDGER_PATH=data/token_ledger.jsonl
```

## Night Growth v2

```text
Conversation → Reflection(normalize)
  → SemanticBuilder → DecisionEngine
  → Identity / Attention / Transformation
  → Graph(memory_id) → Archive
```

Scheduler:

```python
from backend.modules.night_growth import NightGrowth
ng = NightGrowth(memory_manager)
ng.register_scheduler(interval_seconds=86400, user_id="...")
get_scheduler().start()  # optional in app lifespan
```

## Identity

Versioned under `data/identity/{user_id}/versions/vN.json`.  
`update()` always bumps version; `rollback(n)` creates a new version from snapshot.

## Honest limits

- Semantic builder is **rule-based**, not LLM extraction
- Decision engine is **rule-based** (testable; no LLM sole judge)
- Embedding retrieval needs rows with `embedding` field populated
- Scheduler is in-process; Railway multi-instance needs external cron for production HA
