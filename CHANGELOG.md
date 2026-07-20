# Changelog

本專案遵循 [Semantic Versioning](https://semver.org/)。

## [Unreleased] — Phase 1 foundation

### Added

- 後端 pytest 測試底座與核心單元／整合測試
- 前端 Vitest + Playwright smoke（Mock API）
- GitHub Actions CI（backend / frontend / e2e / secret scan）
- Liveness `/live`、Readiness `/ready`
- 備份／還原／環境變數／發版／回滾文件
- `AGENTS.md` 與 PR 模板
- Request ID 中介層與安全日誌工具
- 語音輸入輸出（既有 feature/voice 已合入 main）

### Fixed

- `HTTPException`（如預算 429）不再被外層吞成 500
- 空回覆與 `[ERROR]` 回覆不再寫入長期記憶

### Known issues

- 提醒預設存 ephemeral `data/reminders.json`（Railway 重啟風險）
- 完整 Supabase 還原演練需人工執行

## [1.0.1] — prior

- 小宸光 Web 對話、記憶、工具、語音等功能基線（見 README）
