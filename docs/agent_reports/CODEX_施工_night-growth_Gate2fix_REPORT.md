# CODEX 施工報告 — night-growth Gate2fix

## 1. 任務目標

讓 `workflow_dispatch` 不受每日 gate 阻擋，方便人工執行 dry-run；每日 `schedule` 仍須 repository／Environment variable 明確等於字串 `true` 才能進入 job。

## 2. 現況與根因

原 job-level 條件只有：

```yaml
if: vars.NIGHT_GROWTH_DAILY_ENABLED == 'true'
```

因此 variable 未設或為 `false` 時，連人工 `workflow_dispatch` 的 dry-run 都會被整個 job skip，無法進行 Gate 2 的安全手動驗證。

## 3. 修改內容

條件改為：

```yaml
if: ${{ github.event_name == 'workflow_dispatch' || vars.NIGHT_GROWTH_DAILY_ENABLED == 'true' }}
```

並更新三句仍宣稱檔案為 `.disabled`／schedule 未註冊的過時註解。沒有修改 cron、inputs、secrets、payload、timeout、concurrency 或 endpoint。

## 4. 行為矩陣

| Event | Gate variable | Job | Request mode | 結果 |
|---|---|---|---|---|
| `workflow_dispatch` | 缺值／false／true | 執行 | 預設 `dry_run=true` | 可安全測試，不寫入 |
| `workflow_dispatch` | 任意 | 執行 | 人工選 `dry_run=false` | 後端 flag 未開時 403 |
| `schedule` | 缺值或非 `true` | skip | 無請求 | 零 API 花費 |
| `schedule` | 精確 `true` | 執行 | `dry_run=false` | 仍受後端 flag 與冪等／成本上限保護 |

## 5. 成本與安全

- 本 PR 不 dispatch workflow，不產生 OpenAI API 呼叫。
- 手動入口預設 dry-run，payload 仍固定 `force: false`。
- 非 dry-run 端點仍執行 `if not body.dry_run and not _live_runs_enabled(): 403`。
- Schedule 不因本修正繞過 `NIGHT_GROWTH_DAILY_ENABLED`。
- 唯讀平台核對：兩層 gate variable 目前皆未設定，故 schedule fail closed。

## 6. 影響範圍

只影響 Night Growth workflow 的 job admission。聊天、記憶、人格、反思管線、資料庫、前端與 API contract 均未修改。

## 7. 驗證

- YAML parse 通過。
- 靜態事件矩陣確認 manual=true、schedule 仍需 gate=true。
- 靜態確認 `dry_run` input 預設 true、payload `force: false`。
- 後端 403 保護程式仍存在。
- `git diff --check` 通過。
- Draft PR CI 作為 repo 全回歸最終證據。

## 8. 部署證據

無。本批只建立 Draft PR，未 merge、未 deploy、未 dispatch。

## 9. 風險與回滾

持有 workflow dispatch 權限的人可以手動選 `dry_run=false`；但在伺服器 `NIGHT_GROWTH_ENABLED` 未開時會被 403 擋下。回滾只需 revert 本 commit，恢復原 job-level 條件。

## 10. 白話摘要

現在可以手動按鈕做不花錢的 dry-run 測試；每日鬧鐘仍鎖住。即使手動誤選真實執行，後端總開關沒開也會拒絕。
