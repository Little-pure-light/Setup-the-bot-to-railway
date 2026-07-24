# Memory System V2

Version: 2.0 (Agent Edition)  
Status: Implemented (Strangler / coexist with V1)

## Goal

可演化的 Cognitive Memory System，**不破壞**既有 `MemorySystem` 與 Chat / OpenAI-compatible API。

## Architecture

```text
Chat / Kernel / OpenAI-compat
        │
        ▼
 build_memory_backend()     ← MEMORY_V2_ENABLED?
        │
   ┌────┴────┐
   ▼         ▼
  V1        MemoryManager.as_legacy()
MemorySystem    │
                ├─ MemoryClassifier
                ├─ RetrievalEngine
                ├─ GraphManager
                └─ NightGrowth (offline)
```

## Memory Types

| Type | Purpose |
|------|---------|
| episodic | 對話事件 |
| semantic | 抽象知識 |
| identity | AI 身份 |
| emotion | 情緒 |
| reflection | 反思 |
| transformation | 人格變化 |
| attention | 注意力權重 |
| causal | 因果關係 |

V1 rows continue to use `memory_type=conversation`.

## Modules

| File | Role |
|------|------|
| `backend/modules/memory_manager.py` | save / retrieve / update / archive / delete |
| `backend/modules/memory_classifier.py` | classify → type/importance/confidence/tags/relations |
| `backend/modules/retrieval_engine.py` | type-aware retrieve + V1 recall |
| `backend/modules/graph_manager.py` | supports/updates/contradicts/causes/derived_from |
| `backend/modules/night_growth.py` | daily consolidation pipeline |
| `backend/modules/memory_types.py` | constants + models |

## Feature Flag

```text
MEMORY_V2_ENABLED=false   # default: pure V1
MEMORY_V2_ENABLED=true    # chat uses V2 façade (still writes V1 conversation)
```

Optional:

```text
MEMORY_GRAPH_FILE=data/memory_graph.json
```

## Public API (MemoryManager)

- `save(...)` — classify + V1 conversation + typed row
- `retrieve(...)` — RetrievalEngine
- `update(id, fields=...)`
- `archive(id)` — soft archive
- `delete(id)`

When V2 is enabled, chat calls **LegacyMemoryAdapter.save_memory / recall_memories**, which delegate to Manager (not raw V1-only path).

## Night Growth

Pipeline: Reflection → Semantic → Identity → Attention → Transformation → Graph.

```bash
# dry conceptual self-check
python scripts/migrate_memory_v2.py --self-check

# print optional SQL indexes
python scripts/migrate_memory_v2.py --print-sql
```

Schedule (Railway cron / external): call `NightGrowth(manager).run_once(user_id=...)` once per day.

## Migration Phases (status)

| Phase | Spec | Status |
|-------|------|--------|
| 1 MemoryManager + keep V1 | yes | done |
| 2 MemoryClassifier | yes | done |
| 3 Graph | yes | done |
| 4 Night Growth | yes | done (callable; schedule external) |

## Acceptance

- Existing APIs unchanged paths
- `user_id` / conversation continuity preserved via V1 writes
- Open WebUI `/v1` unaffected (same chat())
- V1 + V2 coexist
- Unit tests for classifier/manager/graph/retrieval/night_growth

## Rollback

Set `MEMORY_V2_ENABLED=false` (or unset). No schema down-migration required for graph (Redis/file).
