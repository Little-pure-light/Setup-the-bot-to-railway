# 第一階段進度

| 任務 | 狀態 | Commit | 測試 | 備註 |
|------|------|--------|------|------|
| P1-01 | 完成 | ec6a07f | pytest 底座 | 測試結構 |
| P1-02 | 完成 | ec6a07f | 核心單元 | calc/registry/emotion/token |
| P1-03 | 完成 | 0d1c3f7 | API 整合 | 含 429 修正 |
| P1-04 | 完成 | 126f54b | Streaming | 協議/meta/event |
| P1-05 | 完成 | 943cbf7 | Tools | 六大工具+安全 |
| P1-06 | 完成 | d42c4c7 | Memory | 隔離+空回覆不存 |
| P1-07 | 完成 | b4f2f72 | Vitest 15 | Chat/History/Login |
| P1-08 | 完成 | fc611fe | Playwright 9 | Mock fetch |
| P1-09 | 完成 | 5cb6d27 | CI yml | push 後看 Actions |
| P1-10 | 完成 | b8db763 | /live /ready | 不耗 token |
| P1-11 | 完成 | 7ad4af3 | BACKUP/RESTORE | 還原演練=需人工 |
| P1-12 | 完成 | ed80734 | AGENTS + PR | |
| P1-13 | 完成 | a3e0676 | CHANGELOG 等 | 未發正式 Release |
| P1-14 | 完成 | 7883978 | logging_utils | Request ID |

## 需人工驗收

- Supabase 完整還原演練（`docs/RESTORE.md`）
- Railway 部署後 `/live` `/ready` 與正式聊天 Smoke
- GitHub Actions 首次 push 後確認狀態
