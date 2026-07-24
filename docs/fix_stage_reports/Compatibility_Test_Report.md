# Compatibility Test Report

## Local pytest

```text
python -m pytest tests/ -q
→ full suite PASS (2026-07-24)
```

Includes: chat API integration, streaming, kernel parity, OpenAI compat, Memory V1/V2, fix-stage units.

## API surfaces

| Surface | Expectation | Result |
|---------|-------------|--------|
| POST /api/chat | No breaking change | Optional `reflection_status` only when `include_reflection=true` |
| /v1/chat/completions | Unchanged contract | Covered by existing tests |
| Open WebUI | Via /v1 | No adapter break |
| user_id / conversation | Preserved | Isolation tests for retrieval |
| Redis | Same service | No migration |

## New surface

`POST /internal/night-growth/run` — internal only; not part of public chat contract.
