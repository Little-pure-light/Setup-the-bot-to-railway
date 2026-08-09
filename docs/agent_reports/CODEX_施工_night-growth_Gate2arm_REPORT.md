# CODEX 施工報告 — night-growth Gate2arm

## 1. 任務目標

把既有 disabled Night Growth workflow 原樣改名為 GitHub 可辨識的 `.yml`，只完成「武裝」，不打開執行 gate、不執行 workflow、不產生 API 花費。

## 2. 現況與安全前檢

- 基準為 PR #41 合併後的 `main` commit `70898fd`。
- Workflow job 有第二層條件：`if: vars.NIGHT_GROWTH_DAILY_ENABLED == 'true'`。
- 實際唯讀查詢結果：repository 層沒有 `NIGHT_GROWTH_DAILY_ENABLED`；`night-growth` Environment variables endpoint 也沒有可讀取的同名值。這比字面 `false` 更精確；在 GitHub expressions 中，缺值不會等於字串 `true`，所以 job 仍被跳過。

## 3. 修改內容

1. 純改名：
   - from `.github/workflows/night-growth-daily.yml.disabled`
   - to `.github/workflows/night-growth-daily.yml`
2. 新增本 STATUS 與 REPORT 到 `docs/agent_reports/`。

沒有修改 workflow 內容、cron、endpoint、payload、secrets 名稱、concurrency、timeout 或 gate 表達式。

## 4. 完整性證據

- 改名前 SHA-256：`F4BB028946FB3D9ADD6FD755966948E854A7F525CF4C6E90C24FDCABC1277F45`
- 改名後 SHA-256：`F4BB028946FB3D9ADD6FD755966948E854A7F525CF4C6E90C24FDCABC1277F45`
- Hash 相同，證明檔案內容未變。
- Git diff 應辨識為 100% rename；另只新增兩份報告。

## 5. 延伸影響

- 合併後 GitHub 會辨識 workflow 與每日 cron 定義。
- 因 job-level gate 不是 `true`，scheduled／manual event 即使被建立，trigger job 仍不執行，不會呼叫 Railway endpoint。
- 本次不影響聊天、記憶、人格、反思管線、前端、資料庫或既有 API。

## 6. 測試與驗證

- 檔案 hash 前後一致。
- 靜態確認 workflow 仍含精確 gate：`vars.NIGHT_GROWTH_DAILY_ENABLED == 'true'`。
- 靜態確認 payload 仍為 `force: false`。
- YAML 僅改名、內容沿用已通過 Gate 1 review／CI 的原始 blob。
- Draft PR CI 作為 repo 全回歸最終證據；本批不手動 dispatch workflow。

## 7. 部署證據

無。這是 Draft PR，尚未 merge／deploy；也沒有執行 Night Growth。

## 8. 未完成與限制

- 本批不建立或設定 `NIGHT_GROWTH_DAILY_ENABLED=false`。若 owner 要求平台上明確顯示 false，應另做平台設定批次；目前缺值已安全 fail closed。
- 本批不驗證正式 endpoint、token、user id 或第一次 dry-run，因為那會跨入後續啟用／驗證 Gate。

## 9. 風險與回滾

主要風險是未來有人把 variable 設為字串 `true`，屆時 scheduled job 才會執行。回滾只需把 `.github/workflows/night-growth-daily.yml` 改回 `.yml.disabled`，不涉及資料或 schema 回滾。

## 10. 白話摘要

鬧鐘的檔案已從「GitHub 看不見」改成「GitHub 看得見」，但電源閘門沒有打開。現在不會整理記憶、不會呼叫 API，也不會花錢。
