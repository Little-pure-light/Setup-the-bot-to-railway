# 靜默反思引擎 Gate 2 啟用 Runbook

> Gate 1 狀態：**未啟用**。本文件不是 Gate 2 授權；只有 owner 看過成本與風險後明確批准才能操作。

## 建議觸發方式

採 GitHub Actions，每日 03:17 Asia/Taipei 觸發 Railway 既有內部端點。理由：執行紀錄集中、失敗可見、不需新增常駐服務，owner 日後只需看 Actions 結果。Railway Cron 少一層網路，但需額外服務／部署設定，操作與回滾較難；應用內 scheduler 在多 replica 可能雙跑，不採用。

## Gate 2 前檢

1. Draft PR 已由獨立 reviewer 通過且 main CI 全綠。
2. 確認 `IDENTITY_UPDATE_MODE=candidate`。
3. 保持以下保守上限：20 turns、5 conversations、約 12000 input tokens。
4. 建立 `night-growth` GitHub Environment，並由 owner 設定 endpoint、內部 token、user id；秘密值不得放進 repo 或日誌。
5. Repository variable `NIGHT_GROWTH_DAILY_ENABLED` 先保持 `false`；Railway `NIGHT_GROWTH_ENABLED` 先保持 `false`。

## 啟用順序（需 owner 明確批准）

1. 將 `.github/workflows/night-growth-daily.yml.disabled` 改名為 `.yml`，先保持 repository variable=false。
2. 合併並確認 main CI；此時排程 job 仍因 variable gate 不執行。
3. Railway 設 `NIGHT_GROWTH_ENABLED=true` 並 redeploy。
4. 先手動 `workflow_dispatch`，選 `dry_run=true`；確認 `completed_dry_run`、所有 stage `ok`、`saved_count=0`，且沒有真實 API 用量。
5. owner 再批准一次真實驗證後，手動選 `dry_run=false`，不得 `force=true`。檢查 `usage`、執行時間、候選 identity 與實際帳單。
6. 真實驗證通過且成本可接受後，才把 `NIGHT_GROWTH_DAILY_ENABLED=true`，使每日排程生效。

## 每次必看欄位

- `status`、`steps`、`usage.turns_processed`、`usage.turns_dropped`
- `usage.estimated_input_tokens`、`usage.saved_count`、`usage.identity_candidates_count`
- `error`；日誌只應有計數，不能有對話、token、user id 或 secret

## 失敗立即關回

1. 把 `NIGHT_GROWTH_DAILY_ENABLED=false`。
2. 把 Railway `NIGHT_GROWTH_ENABLED=false` 並 redeploy。
3. 保留 execution id 與去敏計數；不重跑、不設 `force=true`，先查原因。

## 回滾

移除／重新改名 workflow、保持兩個 enable flag=false，並 revert Gate 1 commit。Gate 1 沒有 schema migration；既有候選與 execution record 可保留供稽核，不需刪資料。
