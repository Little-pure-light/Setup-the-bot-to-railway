# 第一階段進度

| 任務 | 狀態 | Commit | 測試 | 備註 |
|------|------|--------|------|------|
| P1-01 | 完成 | ec6a07f | pytest 底座 | 測試結構 |
| P1-02 | 完成 | ec6a07f | 核心單元 | calc/registry/emotion/token |
| P1-03 | 完成 | 0d1c3f7 | API 整合 | 含 429 修正 |
| P1-04 | 完成 | 126f54b | Streaming | 協議/meta/event |
| P1-05 | 完成 | 943cbf7 | Tools | 六大工具+安全 |
| P1-06 | 完成 | d42c4c7 | Memory | 隔離+空回覆不存 |
| P1-07 | 完成 | b4f2f72 | Vitest | Chat/History/Login + errorSanitize |
| P1-08 | 完成 | fc611fe | Playwright | **Chromium mobile viewport**；尚未驗證 WebKit / 實體 iPhone |
| P1-09 | 需驗證 | 5cb6d27 | CI yml | **Actions 綠燈前不得標完成** |
| P1-10 | 完成 | b8db763 | /live /ready | 設定層級；非完整 DB 探測 |
| P1-11 | 需人工驗收 | 7ad4af3 | BACKUP/RESTORE | Supabase 還原尚未實作演練 |
| P1-12 | 完成 | ed80734 | AGENTS + PR | |
| P1-13 | 完成 | a3e0676 | CHANGELOG 等 | 未發正式 Release |
| P1-14 | 完成 | 7883978 | logging_utils | RedactingFilter 不保證 exc_info |

## 需人工驗收

- Supabase 完整還原演練（`docs/RESTORE.md`）— **尚未執行**
- Railway 部署後 `/live` `/ready` 與正式聊天 Smoke
- GitHub Actions 全部 job 綠燈後，才可將 P1-09 改為「完成」
- WebKit / 實體 iPhone 語音與版面（P1-08 僅 Chromium viewport）

## 健康檢查解讀

- `/ready` 的 `supabase: config_only` / `dns_ok` **不代表**資料庫可讀寫
- Redis `configured` **不代表** PING 成功
