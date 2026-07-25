# Graph Utilization Report — Quality Improvement v1.0

## Goal

Graph must **participate in answers**, not only store edges.

## Before

- Expansion produced stub lines: `related_memory:{id} via {relation}`
- Graph weight in rank only **0.10**
- Little proof that graph improved answer quality

## After

1. Collect neighbor ids from seed hits  
2. **Hydrate** neighbor rows (user_id isolated)  
3. Inject full content into ranked items with `source=graph_expansion`, `via_graph=true`  
4. Raise graph weight to **0.16**  
5. Response meta: `used_graph`, `graph_expanded_count`

## Cases (pattern, n≥10 via tests + logic)

| Scenario | Graph role |
|----------|------------|
| Semantic seed + supports edge | Neighbor knowledge appears in items |
| Duplicate edges | Strongest confidence kept |
| Missing neighbor row | Fallback stub still ranked lower |
| Isolation | Hydrate filters user_id |

Test: `test_graph_expansion_hydrates_content`.

## Schema

**Unchanged** (no new relation types).
