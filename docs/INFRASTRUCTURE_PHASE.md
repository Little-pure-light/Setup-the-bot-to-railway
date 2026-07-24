# Infrastructure Phase

Completed before Memory V2 Phase 2 cognitive upgrades.

## Deliverables

| Module | Path |
|--------|------|
| Reflection Contract | `backend/modules/reflection_contract.py` |
| Token Counter | `backend/modules/token_counter.py` |
| FineTune Dataset | `backend/modules/finetune_dataset.py` |
| Chat Services | `backend/modules/chat_services.py` |

## Reflection Schema (unified)

```json
{
  "summary": "",
  "causes": [],
  "lessons": [],
  "confidence": 0.0,
  "timestamp": ""
}
```

Used by ReflectionStorage, Redis latest payload, FineTune export, Night Growth.

API: `POST /api/chat?include_reflection=true` may include `reflection` field (empty contract when async reflection not yet available — non-breaking).

## Redis Conversation Key

**Only:** `conv:{conversation_id}:latest`

Canonical payload:

- `messages`: `[{role, content}, ...]`
- `summary`: string
- `reflection`: contract object or null
- `updated_at`: ISO8601

Legacy `user_msg` / `assistant_msg` still mirrored for older readers.

## Token Accounting

- tiktoken (cl100k_base fallback)
- Ledger: `data/token_ledger.jsonl` (or `TOKEN_LEDGER_PATH`)
- Not written into message text
- Optional disable: `TOKEN_LEDGER_ENABLED=false`

## FineTune Dataset

- Export JSONL only (no training)
- Filter by user_id / conversation / date
- Validate + statistics APIs in module

## chat_router

Still handles request/response/routing. Side logic moved toward `chat_services` + contracts. Full god-object removal remains technical debt.
