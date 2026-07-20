# 第一階段進度

| 任務 | 狀態 | Commit | 測試 | 備註 |
|------|------|--------|------|------|
| P1-01 | 完成 | ec6a07f | 58→105+ passed | 測試基礎 |
| P1-02 | 完成 | ec6a07f | 同上 | 核心單元測試 |
| P1-03 | 完成 | 0d1c3f7 | API 整合 | 預算 429 修正 |
| P1-04 | 完成 | 126f54b | Streaming | 協議解析 |
| P1-05 | 完成 | 943cbf7 | Tools | 內建工具 |
| P1-06 | 完成 | d42c4c7 | Memory | 空/[ERROR] 不存 |
| P1-07 | 完成 | （本輪） | Vitest 15 | Chat/History/Login |
| P1-08 | 完成 | （本輪） | Playwright 9 | Desktop/iPhone/Pixel mock |
| P1-09 | 完成 | （本輪） | CI workflow | 需 push 後 GitHub 綠燈 |
| P1-10 | 完成 | （本輪） | /live /ready | 不耗 token |
| P1-11 | 完成 | （本輪） | 文件 | 還原演練=需人工 |
| P1-12 | 完成 | （本輪） | AGENTS + PR | |
| P1-13 | 完成 | （本輪） | CHANGELOG/RELEASE | 未打正式 tag |
| P1-14 | 完成 | （本輪） | logging_utils | Request ID |

## 需人工驗收

- Supabase 完整還原演練（`docs/RESTORE.md`）
- Railway 部署後 `/live` `/ready` 與正式聊天 Smoke
- GitHub Actions 首次 push 後確認 gitleaks / pip-audit 警告是否可接受
