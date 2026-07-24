# Identity Charter Implementation Report

## Schema

Charter fields: `identity_id`, `version`, `name`, `role`, `mission[]`, `core_values[]`,
`principles[]`, `boundaries[]`, `capabilities[]`, `limitations[]`,
`communication_style{}`, `personality_traits{}`, `relationship_context{}`,
`growth_history[]`, timestamps, `previous_version_id`, `change_reason`, `confidence`.

## Behaviors

| Operation | Behavior |
|-----------|----------|
| load | Normalize legacy → Charter; bootstrap v1 if missing |
| update | Requires `change_reason`; version bump or candidate |
| low confidence / candidate mode | Write candidate only |
| identical content | `noop` |
| rollback | New formal version restoring old content |
| compare_versions | Field-level diffs |
| change_history | JSONL append-only |
| to_prompt_fragment | Context only — **does not set system prompt** |

## Env

- `IDENTITY_UPDATE_MODE=candidate` (staging default)
- `IDENTITY_CONFIDENCE_THRESHOLD=0.6`

## Tests

`tests/unit/test_memory_v2_fix_stage.py` — charter, reject missing reason, candidate, noop, rollback, compare.
