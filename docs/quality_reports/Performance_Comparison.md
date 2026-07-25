# Performance Comparison — Before → After

Date: 2026-07-25  
Suite: `pytest tests/` **PASS** (full)

## Quantitative

| Metric | Before | After |
|--------|--------|-------|
| Typed write on pure chitchat | Usually yes | **No** (`should_persist=false`) |
| 100-turn typed persist rate | ~100% | **&lt;45%** (unit-enforced) |
| Rank: importance weight | 0.15 | **0.20** |
| Rank: graph weight | 0.10 | **0.16** |
| Rank: recency weight | 0.15 | **0.12** |
| Reflection lessons field | Weak / emoji improvements | **Actionable `lessons[]`** |
| Graph hydrate content | No | **Yes** |
| Identity root-cause fix | Unanalyzed | **Documented + multi-signal path** |
| New APIs | — | **0** |
| New memory types | — | **0** |

## Qualitative

| Area | Change |
|------|--------|
| Memory pollution | ↓ low-value permanent rows |
| Retrieval | First hit favors relevance + importance |
| Reflection | Insight + next action |
| Identity | Candidates from real signals without lowering conf floor |
| Graph | Actually used in retrieval path |

## Risk

- Stricter typed gate may reduce some medium episodic saves — intentional.  
- V1 conversation continuity **unchanged**.  
- §9 surfaces preserved (no API break).
