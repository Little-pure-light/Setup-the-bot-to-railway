# Reflection Quality Report — Quality Improvement v1.0

## Goal

Reflection = **insight**, not hollow chat summary.

## Before

| Issue | Example |
|-------|---------|
| Summary style | Decorative, “已進行 N 層分析” without next action |
| Lessons | Often only `improvements` emoji list; contract `lessons` weak |
| Hollow | “基本達標” style causes |
| Merge | No multi-source merge / quality score |

## After

| Change | Effect |
|--------|--------|
| `_synthesize_summary` | Must include 核心發現 + 後續方向 |
| `_to_actionable_lessons` | Explicit `lessons[]` with “下次回應時…” |
| `reflection_quality_score` | 0..1 insight score + flags |
| `merge_reflections` | Dedupe causes/lessons; pick best summary |
| `is_actionable_reflection` | Gate for identity / knowledge paths |
| Decision engine | Hollow reflection does not force identity |

## Before / After samples (schema-level, n≥10 pattern)

| # | Before-like | After-like |
|---|-------------|------------|
| 1 | 還可以 | 核心發現：…後續方向：… |
| 2 | improvements only | lessons + improvements |
| 3 | confidence 0.6 hollow | quality score flags no_lessons |
| 4–10 | merge empty / dup | merge_reflections dedupe |

Automated: `test_reflection_has_insight_not_hollow`, `test_merge_reflections_dedupes`.

## API

**Unchanged.** Only generation + contract helpers.
