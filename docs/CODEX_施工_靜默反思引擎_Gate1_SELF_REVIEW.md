# CODEX 自我審查 — 靜默反思引擎 Gate 1

## 判定

**LOCAL PASS / WAITING FOR DRAFT PR CI AND CLAUDE INDEPENDENT REVIEW**

## 驗收逐項

- [x] 最新 `origin/main` 建乾淨 worktree 與獨立 branch。
- [x] 管線、端點、idempotency、鎖、identity candidate、enable flag 基準已核對。
- [x] dry-run 假資料 E2E 全 stage ok，零寫入、零真實 API。
- [x] turn／conversation／token 三層上限與硬上限有 deterministic 測試。
- [x] 非 dry-run 有 server-side master flag，預設 fail closed。
- [x] 去敏 usage report／log 不含原文與身分 id。
- [x] identity candidate 不自動升 formal。
- [x] 每日觸發模板實際 disabled，另有第二層 repository variable gate。
- [x] Gate 2 Runbook 含先 dry-run、單次 live、看成本、失敗關回。
- [x] 後端 440 tests、前端 31 tests、build 通過。
- [ ] Draft PR CI：push 後確認。
- [ ] Claude 獨立逐檔複核：PR 交付後執行。

## 反向思考

- 若有人只把 workflow 改名但忘了 variable，job 被 `NIGHT_GROWTH_DAILY_ENABLED` 擋住。
- 若有人只開 variable但後端 flag 未開，非 dry-run 被 403 擋住。
- 若重複排程，同日冪等與 workflow concurrency 共同防重；不得以 `force=true` 繞過。
- 若輸入暴增，優先保留最新資料且不突破三層上限。
- 若 identity 訊號成立，candidate 模式只產候選，不改 current charter。
- 若日誌外洩風險上升，本次新增 summary 只有 status、dry_run 與數量。

## 未解風險

1. 既有 npm audit findings 需另案升級依賴，不宜混入本 PR。
2. 既有 pytest warnings 需另案修正 AsyncMock fixture 與 Starlette/httpx 相容性。
3. 第一次 live 的真實 embedding 數與帳單只能在 Gate 2 owner 批准後量測。
4. `.disabled` 模板尚未在 GitHub runner 執行；真正改名啟用前須由 reviewer 再看 YAML 與 secrets 邊界。

## 回滾確認

本變更沒有 schema migration。停用旗標預設 false；revert 單一 commit 即回到原行為。既有 memory、identity current、graph 與 archive 資料格式未改。
