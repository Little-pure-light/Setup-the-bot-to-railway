# §9 Memory V2 Verification — Partial (blocked on auth)

Date: 2026-07-25  
Target backend: `https://ai2.dreamground.net`  
Open WebUI: `https://open-webui-production-df5b.up.railway.app`  
Commit: `791506dd64500677ed6a264b893e259e5371195d`

## Status

**BLOCKED** after public checks — no `API_SECRET` / `NIGHT_GROWTH_INTERNAL_TOKEN` available to the verification agent.

## 9.1 Public / infra (completed without auth)

| Check | Result | Notes |
|-------|--------|-------|
| `/health` | PASS | `status=ok`, git_commit matches push |
| `/ready` | PASS (degraded) | app/openai/supabase config ok |
| Redis | **FAIL / degraded** | `redis: unavailable` on readiness |
| Supabase | config present | readiness is config-only probe, not DB ping |
| OpenAI key | configured | presence only |
| `POST /api/chat` without token | 401 | auth enforced |
| `GET /v1/models` without token | 401 | auth enforced |
| `POST /internal/night-growth/run` without token | 401 | auth enforced |
| Open WebUI `/api/config` | PASS | v0.10.2, login form on |

## 9.1–9.4 Authenticated (not run)

Requires Bearer token:

- `/api/chat` stream/non-stream
- `/v1/chat/completions`
- Memory V2 scenarios (name, preference, emotion, knowledge, recall, night growth)
- user isolation A/B
- Night Growth dry_run / formal / idempotency
- include_reflection → reflection_status

## How to unblock

Provide `API_SECRET` (same as Open WebUI API Key) to the agent session **without pasting into public channels if possible**:

```powershell
$env:API_SECRET = "<your Railway API_SECRET>"
$env:BASE_URL = "https://ai2.dreamground.net"
# optional if different from API_SECRET:
# $env:NIGHT_GROWTH_INTERNAL_TOKEN = "<token>"
cd "C:\Users\playh\AI Data\LanguageModules\孵化器主程式完整版\Setup-the-bot-to-railway"
python scripts/verify_memory_v2_staging.py
```

Or reply in chat that the secret is ready in a local-only path / env, and ask the agent to re-run.

## Script prepared

`scripts/verify_memory_v2_staging.py` — full §9 matrix with isolated `staging_verify_*` users.
