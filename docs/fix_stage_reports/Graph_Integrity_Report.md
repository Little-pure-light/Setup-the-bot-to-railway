# Graph Integrity Report

## Edge schema

`source_memory_id`, `target_memory_id`, `relation` ∈ {supports, updates, contradicts, causes, derived_from},
`confidence`, `created_at`, `created_by`, `metadata` (+ legacy timestamp/meta aliases).

## Rules

- Forbidden label nodes (`reflection`, `document`, …)
- Duplicate active edges suppressed
- Archive/delete memory → archive/remove related edges (no live orphans)

## Tool

```bash
python scripts/check_memory_graph_integrity.py
python scripts/check_memory_graph_integrity.py --all-users
```

Outputs: total_nodes, total_edges, orphan_edges, invalid_relations, missing_memory_ids, duplicate_edges.

Local check (empty graph): `ok: true`.
