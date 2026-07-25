# Memory Quality Report — Quality Improvement v1.0

Date: 2026-07-25  
Scope: Task A (Classifier) + write gate  
Constraint: no new API / memory type / DB

## Goal

Not remember more — **remember better**.

## Before

| Metric | Approx |
|--------|--------|
| Typed permanent write policy | Nearly every dialogue turn with text → typed row |
| Chitchat / 謝謝 / 你好 | Often stored as episodic typed |
| Preference / self-intro | No special tier boost |
| `value_tier` | N/A |

## After

| Metric | Value (100-turn synthetic mix) |
|--------|--------------------------------|
| High tier | measured in unit test ≥5 |
| Low tier | majority of pure chitchat |
| `should_persist` typed | **&lt; 45 / 100** (was ~100) |
| Skip typed permanent | chitchat / courtesy / trivial |

100-turn mixture: names, prefs, knowledge Q, 謝謝, 你好, 哈哈, 嗯.

## Write policy

| Tier | Typed V2 permanent | Examples |
|------|--------------------|----------|
| High | Yes | self-intro, preference, attention, strong reflection |
| Medium | Yes | semantic/knowledge, solid episodic |
| Low | **No** (V1 continuity only) | 你好, 謝謝, 嗯, empty small talk |

## Files

- `backend/modules/memory_classifier.py`
- `backend/modules/memory_types.py` (`value_tier`, `should_persist`)
- `backend/modules/memory_manager.py` (persist gate)

## Tests

`tests/unit/test_memory_v2_quality.py` — chitchat low, preference persist, 100-turn volume.
