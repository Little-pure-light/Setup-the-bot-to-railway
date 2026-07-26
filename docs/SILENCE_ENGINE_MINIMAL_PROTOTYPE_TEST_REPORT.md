# Silence Engine Minimal Prototype — Test Report

**Date:** 2026-07-26  
**Branch:** `feature/silence-engine-minimal-prototype`  
**Module:** `backend/silence_engine.py`  
**Command:** `python -m pytest tests/unit/test_silence_engine.py -v`  
**Second LLM call:** **No**  
**Production deploy:** **No**  
**Implementation PR:** **Not opened** (awaiting user approval of this report)

---

## 1. Documentation PR (Gate A)

| Item | Value |
|------|--------|
| Status | **有，已 push** |
| PR | https://github.com/Little-pure-light/Setup-the-bot-to-railway/pull/15 |
| Branch | `docs/silence-and-timing-analysis` |
| Files | 6× `docs/*` only (no runtime code) |

Note: Exec book suggested branch name `docs/silence-engine-research`; research docs were delivered via PR #15 instead. Content includes the three silence research reports plus timing/perf docs.

---

## 2. Test totals

| Metric | Value |
|--------|-------|
| Collected | **27** |
| Passed | **27** |
| Failed | **0** |
| Duration | ~0.38s |

---

## 3. Mode verification

| Mode | Result | Evidence |
|------|--------|----------|
| **OFF** (default) | Pass | `test_default_master_switch_off`, `test_disabled_does_not_mutate_messages` |
| **Observe** | Pass — route selected, messages unchanged | `test_observe_logs_only_no_framing` |
| **Shadow** | Pass — no user-visible change | `test_shadow_no_user_visible_change` |
| **Active + allowlist** | Pass — framing applied | `test_active_allowlist_applies_framing` |
| **Active − allowlist** | Pass — no framing | `test_active_without_allowlist_no_framing` |

---

## 4. Route results (S01–S14 + FP/FN)

### S01–S14 (`test_s01_s14_fixtures`)

| ID | Expect | Result |
|----|--------|--------|
| S01 忙？ | C1n | Pass |
| S02 算了沒事 | C1n | Pass |
| S03 想知道 | none (C7 out) | Pass |
| S04 拒絕 | none (C7 out) | Pass |
| S05 效率 | C2 | Pass |
| S06 我很好 | C1n | Pass |
| S07 誠實/保護 | C3n | Pass |
| S08 一定答應 | C3n | Pass |
| S09 那個東西 | none (C6 out) | Pass |
| S10 上次計畫 | none | Pass |
| S11 天氣 | bypass fact | Pass |
| S12 電影 | none | Pass |
| S13 辭職 | C3n | Pass |
| S14 1+1 | bypass arithmetic | Pass |

### False positives (≥2 per route)

| Route | Negatives that must not select route | Result |
|-------|--------------------------------------|--------|
| C1n | Python 排序函式；翻譯成中文 | Pass |
| C2 | 天氣；1+1 | Pass |
| C3n | 推薦電影；現在幾點 | Pass |

### False negatives (≥2 per route)

| Route | Must select | Result |
|-------|-------------|--------|
| C1n | 算了沒事；最近忙 | Pass |
| C2 | 更有效率；更專注 | Pass |
| C3n | 誠實/保護；該不該辭職 | Pass |

### Bypass / direct exit

Arithmetic, closed fact, direct command, urgent, empty — **Pass**.

---

## 5. Latency (module only; no artificial wait)

From `test_no_artificial_delay_and_latency_budget` (150 samples, active mode):

| Metric | Budget | Observed (typical run) |
|--------|--------|-------------------------|
| Median | < 20 ms | **0.014 ms** (rules only) |
| Max | < 100 ms | **0.541 ms** |
| `silence_engine_ms` | < 50 | Pass |
| `time.sleep` / `asyncio.sleep` in module | Forbidden | **Absent** |

---

## 6. Concurrency

`test_concurrent_evaluate_stable` — 40 parallel evaluates, all C1n + apply on allowlist — **Pass**.  
Does not create HTTP duplicate requests (pure function).

---

## 7. Changed files (implementation branch)

| Path | Role |
|------|------|
| `backend/silence_engine.py` | **New** module |
| `backend/chat_router.py` | Thin hook after `build_prompt` |
| `docs/ENVIRONMENT_VARIABLES.md` | Env rows |
| `docs/SILENCE_ENGINE_MINIMAL_PROTOTYPE_DESIGN.md` | Design |
| `docs/SILENCE_ENGINE_MINIMAL_PROTOTYPE_TEST_REPORT.md` | This report |
| `tests/fixtures/silence_s01_s14.json` | Fixtures |
| `tests/unit/test_silence_engine.py` | Tests |

**Not included:** `scripts/perf_acceptance_run.py` (unrelated functional script).

---

## 8. Gates checklist

| Gate | Status |
|------|--------|
| A Documentation history | ✅ PR #15 |
| B Feature off unchanged | ✅ |
| C Observe | ✅ |
| D Shadow | ✅ |
| E Active allowlist | ✅ |
| F Bypass correctness | ✅ |
| G No performance theater | ✅ |
| H No uncontrolled interpretation (≤2 hyp) | ✅ |
| I No Production deploy | ✅ |
| J User approval before impl PR | ⏳ **waiting** |

---

## 9. 一竅哥八件事

1. 研究文件獨立 PR、無混入程式碼 → **是（PR #15）**  
2. 功能預設關閉 → **是**  
3. 關閉時聊天不變 → **是（測試）**  
4. Observe 只記錄不改答案 → **是**  
5. Shadow 可比較、使用者仍原答案 → **是**  
6. 無 sleep／倒數／省略號思考 → **是**  
7. 事實／計算不啟動 → **是**  
8. 批准前未部署／未開實作 PR／未合併 → **是**

---

*Awaiting user approval before `git push` of feature branch or opening an implementation PR.*
