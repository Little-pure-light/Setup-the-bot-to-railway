# Silence Engine Minimal Prototype — Design Note

**Branch (implementation):** `feature/silence-engine-minimal-prototype`  
**Docs research PR:** https://github.com/Little-pure-light/Setup-the-bot-to-railway/pull/15  
**Status:** Prototype only. **Default OFF. Do not deploy to Production without explicit approval.**

## Goal

Optional, **observable response-path switch** that can suspend the first automatic answer framing and allow a different **choice structure** (C1n / C2 / C3n).

**Not a delay effect.** No fixed/random sleep, countdown, fake typing, ellipsis theater, or wall-clock waiting.

## Module boundary

| Piece | Location |
|-------|----------|
| Core logic | `backend/silence_engine.py` (dedicated, removable) |
| Integration | `backend/chat_router.py` — single call after `build_prompt` |
| Fixtures | `tests/fixtures/silence_s01_s14.json` |
| Tests | `tests/unit/test_silence_engine.py` |

When `SILENCE_ENGINE_ENABLED=false` (default), `run_silence_for_chat` returns immediately without mutating messages.

## Decision flow (actual)

```
user_message
  → master disabled? → no-op
  → C5 bypass (fact / arithmetic / direct command / urgent / empty)?
  → score C1n / C2 / C3n (rule-based, no 2nd LLM)
  → confidence < MIN? → none
  → mode:
       observe → log only, answer path unchanged
       shadow  → log / metadata, answer path unchanged
       active  → apply framing only if allowlisted
  → optional inject framing into system message
  → record silence_engine_ms (module CPU only)
```

Mapped into Legacy `chat()` after prompt build; Kernel path is unchanged in this prototype (flag off by default globally).

## Approved routes

| ID | Behavior |
|----|----------|
| **C1n** | ≤2 relational hypotheses; never claim mind-read as fact |
| **C2** | Task vs load fork; **must** offer direct-answer exit |
| **C3n** | Expand values then **must** return to actionable next step |
| **C5** | Mandatory bypass |

Out of scope here: C4 (safety/policy), C6 (memory/clarification), C7 (more experiments).

## Second LLM call

**Not used.** Framing is a system-prompt instruction only.

## Observability fields

See `SilenceDecision.public_metadata()`:

`silence_engine_enabled`, `silence_engine_mode`, `silence_route_candidate`, `silence_route_selected`, `silence_bypass_reason`, `silence_confidence`, `silence_structure_changed`, `silence_direct_exit_offered`, `silence_engine_ms`, plus allowlist/apply flags.

No hidden chain-of-thought is logged.

## Env (defaults)

```text
SILENCE_ENGINE_ENABLED=false
SILENCE_ENGINE_MODE=observe
SILENCE_ENGINE_ALLOWLIST=
SILENCE_ENGINE_MIN_CONFIDENCE=0.75
SILENCE_ENGINE_MAX_HYPOTHESES=2
SILENCE_ENGINE_LOGGING_ENABLED=true
```

## Removal

1. Delete `backend/silence_engine.py`  
2. Remove the short integration block in `chat_router.py`  
3. Remove tests/fixtures/env rows  

No schema, personality, or safety policy changes.

## Acceptance gates (self-check)

| Gate | Met by |
|------|--------|
| A Docs-only PR | PR #15 |
| B Feature off | default + tests |
| C Observe | mode=observe tests |
| D Shadow | mode=shadow tests |
| E Active allowlist | allowlist tests |
| F Bypass | C5 tests + S11/S14 |
| G No theater | no sleep in module + latency test |
| H Limited hypotheses | MAX_HYPOTHESES≤2 |
| I No Production deploy | this task |
| J No impl PR until user approves test report | hold PR |
