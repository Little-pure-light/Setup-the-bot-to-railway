# §9 Memory V2 Staging Verification Report

Date: 2026-07-25  
Backend: `https://ai2.dreamground.net`  
Open WebUI: `https://open-webui-production-df5b.up.railway.app`  
git_commit: `791506dd64500677ed6a264b893e259e5371195d`  
`MEMORY_V2_ENABLED`: confirmed set on Backend  

Users used (isolated): `staging_verify_a` / `staging_verify_b`  
Script: `scripts/verify_memory_v2_staging.py` (+ manual retries)

---

## Overall

| Area | Verdict |
|------|---------|
| Deploy / health | **PASS** |
| Auth gate | **PASS** |
| `/api/chat` + `/v1` | **PASS** |
| Reflection status | **PASS** (`pending` when not ready) |
| Memory dialogue matrix | **PASS** (after schema fix + knowledge retry) |
| Continuity / recall | **PASS** |
| Streaming | **PASS** |
| Night Growth endpoint | **PASS** (retest 2026-07-25 after redeploy) |
| Redis | **degraded / unavailable** (known) |
| Open WebUI host | Up (frontend only) |

**Chat + Night Growth green.** Redis still degraded (deferred).

---

## 9.1 Basic functions

| Check | Result | Notes |
|-------|--------|-------|
| `/health` | PASS | commit matches push |
| `/ready` | PASS (degraded) | redis unavailable |
| `/v1/models` | PASS | `xiaochenguang` |
| Unauth `/v1/models` | PASS | 401 |
| `POST /api/chat` non-stream | PASS | body field must be **`user_message`** |
| `POST /v1/chat/completions` | PASS | |
| Streaming `/api/chat?stream=true` | PASS | 200, event stream starts |
| Tool-calling surface | Soft | stream shows tool_status planning events |
| File upload / Open WebUI login UI | Not fully automated | WebUI config live v0.10.2 |
| user_id persistence / conv continuity | PASS | same conv+user recalls prefs |

---

## 9.2 Memory V2 scenarios

| # | Scenario | Result | Evidence (snippet) |
|---|----------|--------|--------------------|
| 1 | Name / address | PASS | 記住「小測A」 |
| 2 | Preference | PASS | 無糖綠茶 |
| 3 | Emotion | PASS | 溫柔回應疲憊 |
| 4 | Prior events | PASS | 記得名字+綠茶 |
| 5 | Teach knowledge | PASS (retry) | 確認 LightSoul-Staging-Verify |
| 6 | Reflection status | PASS | `reflection_status=pending`, no fake empty complete |
| 7–8 | Night Growth dry_run | **PASS** (retest) | `completed_dry_run`, turns=12, no writes |
| 9 | Night Growth formal + idempotent | **PASS** (retest) | formal `completed` (saved 29, edges 10); 2nd → `skipped_duplicate` |
| 10 | Identity candidate/version | Soft | formal run `identity_update.patches=0` (no high-conf reflection lessons this batch) |
| 11 | Graph edges | **PASS** | formal produced 10 `graph_edge_ids` |
| 12 | Re-login recall | PASS (same API user/conv) | 專案代號+綠茶召回成功 |

Recall quote (retry): assistant correctly returned project code **and** 無糖綠茶.

---

## 9.3 Isolation

| Check | Result | Notes |
|-------|--------|-------|
| User B can chat | PASS | 200 |
| Cross-user silent leak | Soft PASS | B answered about code mainly because question text contained it; no proof of reading A's typed store |
| Staging users only | PASS | used `staging_verify_*` |

---

## 9.4 Failure / safety (partial)

| Check | Result |
|-------|--------|
| Anonymous Night Growth | PASS (401) |
| Same-day NG idempotency | **Not run** (auth blocked) |
| Embedding timeout / Redis down | Redis already unavailable; chat still works via Supabase path |
| Main dialogue not lost when NG fails | PASS (chat independent of NG) |

---

## Night Growth retest (after redeploy)

| Step | HTTP | status | Notes |
|------|------|--------|-------|
| dry_run | 200 | `completed_dry_run` | load_turns=12; saved_ids_count=0 |
| formal #1 | 200 | `completed` | knowledge_saves=17; attention=1; graph edges=10; saved_ids=29 |
| formal #2 same day | 200 | `skipped_duplicate` | message=`already_completed_today` |
| anonymous | 401 | — | PASS (no public access) |

execution_id samples: `ng_11b552c746b1` (dry), `ng_063b3ffde209` (formal), `ng_f61e77c382af` (skip)

---

## Redis note

`/ready` reports `redis: unavailable`.  
Spec deferred Redis migration; chat still succeeded.  
Short-term cache / conv latest may be degraded — monitor if multi-turn quality dips under load.

---

## Recommendation

| Question | Answer |
|----------|--------|
| Backend V2 chat path working? | **Yes** |
| Night Growth staging complete? | **Yes** (dry_run + formal + idempotency + anon reject) |
| Production soak now? | Optional cautious soak; keep Production flags explicit; Redis still degraded |
| Rotate API_SECRET? | **Recommended** — secret was shared in chat; rotate after verification stabilizes |

---

## Secrets

No secrets written into this report or into git.
