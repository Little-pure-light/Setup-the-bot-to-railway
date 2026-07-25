# Retrieval Benchmark Report — Quality Improvement v1.0

## Ranking weight change

| Factor | Before | After |
|--------|--------|-------|
| Vector similarity | 0.40 | **0.36** |
| Importance | 0.15 | **0.20** |
| Type match | 0.20 | **0.16** |
| Graph confidence | 0.10 | **0.16** |
| Recency | 0.15 | **0.12** |

Intent: **first hit = most relevant**, not merely newest.

## Before / After behavior

| Case | Before risk | After |
|------|-------------|-------|
| Old high-importance vs recent noise | Recency could win | Importance + vector dominate |
| Graph edges | Stub `related_memory:id` only | **Hydrate neighbor content** + rank |
| Keyword fallback | 0.85 penalty | 0.82 penalty |

## Benchmark

- ≥20 query variants in `test_retrieval_benchmark_top1`
- Seeded identity / semantic / episodic / reflection rows
- Assert top-hit type alignment better than random

## Files

- `backend/modules/retrieval_engine.py`
