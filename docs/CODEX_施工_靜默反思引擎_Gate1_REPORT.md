# CODEX 施工報告 — 靜默反思引擎 Gate 1

## 1. 任務目標

在不啟用、不排 live cron、不碰正式資料與 secrets、不產生真實 API 費用的前提下，替既有 Night Growth 補上單次成本護欄、去敏用量觀測、停用狀態的每日觸發模板與 deterministic 測試。

## 2. 現況與根因

既有 `NightGrowth.run_once()` 已有完整離線管線：load turns → reflection → semantic builder → decision engine → identity candidate → attention／transformation → graph → archive；也已有同 user/day 冪等、檔案鎖、execution record 與內部 token 端點。

缺口有三個：非 dry-run 端點未再檢查 `NIGHT_GROWTH_ENABLED`、單次輸入量沒有 conversation／turn／token 三層上限、沒有可直接交付但確實不會被 GitHub 註冊的排程模板。

## 3. 修改內容

- `backend/modules/night_growth.py`
  - 預設上限：20 turns、5 conversations、粗估 12000 input tokens。
  - 程式另有不可被環境值突破的硬上限：200／50／100000。
  - 優先保留最新 turns；超量資料不進本次管線。
  - token 估算完全本地執行：CJK 每字至少算 1 token、ASCII 約 4 字元算 1 token，避免低估中文。
  - execution report 與去敏 log 只記處理量、粗估 token、產出數，不記 user id 或對話內容。
- `backend/internal_night_growth_router.py`
  - dry-run 在 master flag 關閉時仍可驗證。
  - 非 dry-run 必須同時通過 token 與 `NIGHT_GROWTH_ENABLED=true`；預設 403 fail closed。
  - 回應增加去敏 `usage`。
- `.github/workflows/night-growth-daily.yml.disabled`
  - 建議方案的完整模板；因副檔名 `.disabled`，Gate 1 push 後也不會成為 Actions workflow。
  - 另有 repository variable gate、Environment、concurrency、timeout、`force=false`。
- 文件與測試
  - 新增 Gate 2 Runbook、環境變數說明、端點 gate／dry-run／成本上限／candidate 測試。

## 4. Dry-run E2E 證據

測試 `test_night_growth_gate1_dry_run_e2e_has_all_stages` 使用單一假對話、fake OpenAI／Supabase、`dry_run=True`。結果：

| Stage | 結果 | 寫入 |
|---|---|---|
| load_turns | ok | 0 |
| reflection | ok | 0 |
| semantic_builder | ok | 0 |
| decision_engine | ok | 0 |
| identity_update | ok | 0；dry-run 不產 candidate |
| attention_update | ok | 0 |
| transformation_update | ok | 0 |
| graph_update | ok | 0 |
| archive | ok | 0 |

總結果：`completed_dry_run`、`saved_ids=[]`、`archived_ids=[]`、`graph_edge_ids=[]`、`outputs_total=0`。這只證明本機安全管線可走完，不代表正式引擎已運作。

## 5. 觸發方案比較

| 方案 | 成本／資源 | 可靠度 | owner 操作難度 | 結論 |
|---|---|---|---|---|
| GitHub Actions → internal endpoint | 不新增常駐服務；依既有 Actions 額度 | 有 run history、失敗可見、concurrency 可控 | 低；只看 Actions 與一個 variable | **建議** |
| Railway Cron | 可能需額外 cron service／設定 | 少一層網路，但平台設定與回滾較分散 | 中 | 備選 |
| 應用內 scheduler | 不需外部呼叫 | 多 replica 有雙跑風險，依賴程序存活 | 高 | 不採用 |

## 6. 粗略成本估算

目前 Night Growth 的 classifier／semantic／decision 本身是本地程式；真實寫入可能透過 `text-embedding-3-small` 產生 embedding，沒有 chat completion。[OpenAI 官方模型頁](https://developers.openai.com/api/docs/models/text-embedding-3-small)在 2026-08-09 顯示 input 每 1M tokens US$0.02。

用保守上界估算：12000 source tokens × 最多約 8 個 typed write 路徑／turn 等效量 ≈ 96000 embedding tokens；約 `96000 / 1,000,000 × US$0.02 = US$0.00192`，即每 run 約千分之幾美元，數量級低於 US$0.01。這不是帳單保證；Supabase、Railway、GitHub 方案費與未來若新增 LLM reflection 都未包含。Gate 2 必須用第一次受控真實 run 的 `usage` 與實際帳單校正，並先重新核對官方單價。

## 7. 測試證據

- `python -m pytest -q --basetemp=.pytest_tmp_gate1_final` → **440 passed**。
- Night Growth／endpoint 針對測試 → **18 passed**。
- `npm.cmd run test` → **31 passed**（7 files）。
- `npm.cmd run build`（`VITE_API_URL=http://localhost:8000`）→ production build PASS。
- `git diff --check` → PASS（僅 Windows LF→CRLF 提示，非 diff error）。

已知警告：完整 pytest 有既存 Starlette `httpx` deprecation，且 4 個聊天／streaming 測試在 `chat_router.py` 產生既存 AsyncMock 未 await warnings；測試仍全綠。`npm ci` 回報既存 lockfile 10 個 audit findings（2 moderate、7 high、1 critical）；本 Gate 不執行可能造成 breaking change 的 `npm audit fix --force`。

## 8. 延伸影響與限制

- 新 gate 會讓過去「只持有 internal token、但 master flag=false」的真實端點呼叫由可執行改為 403；這是刻意的安全收緊。dry-run 不受影響。
- token 是粗估值，不是 OpenAI tokenizer 的精確計費值；採中文保守算法降低超支風險。
- 目前查詢本來只取單一 user 的最近 turns；conversation 上限是未來／顯式 `recent_turns` 的額外保護。
- 沒有正式資料、真實 API、部署或重啟證據，因為這些都明確屬 Gate 2。

## 9. 安全、隱私與人格

- 日誌不含 user id、conversation id、對話、token 或 secret。
- `IDENTITY_UPDATE_MODE=candidate` 測試確認 current identity version 不變，只新增 candidate。
- dry-run 不寫記憶、不佔同日冪等；正式成功後同日第二次仍 `skipped_duplicate`；鎖測試仍通過。
- 沒有 schema migration，沒有刪除或覆寫既有記憶。

## 10. 回滾與白話摘要

回滾只需保持 `NIGHT_GROWTH_ENABLED=false`、不改名 `.disabled` workflow，並 revert 本 Gate commit；無資料 migration 需要反向操作。

白話說：我把「每天整理記憶」的機器裝上了三道限流、安全總開關與只看數字不看內容的儀表，也把鬧鐘先放進盒子裡但沒有插電。現在可以給 Claude 看施工品質；還沒有讓小宸光每天真的跑。
