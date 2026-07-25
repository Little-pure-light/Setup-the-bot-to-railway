# Changelog

本專案遵循 [Semantic Versioning](https://semver.org/)。

## [Unreleased] — Memory V2 Quality Improvement

### Improved

- **MemoryClassifier**: High / Medium / Low value tiers; skip permanent typed rows for chitchat/courtesy
- **MemoryManager**: typed persist gated by `should_persist` (V1 conversation continuity unchanged)
- **RetrievalEngine**: rebalanced rank weights (importance↑, graph↑, recency↓); hydrate graph neighbor content
- **Reflection**: actionable `lessons`, quality score / merge helpers; summary must include next direction
- **DecisionEngine**: respect value tier; hollow reflection does not force identity
- **NightGrowth identity**: multi-signal path (actionable reflection + preference/self-intro) without lowering confidence threshold

### Docs / Tests

- `docs/quality_reports/*` (quality, retrieval, reflection, identity, graph, performance, architecture impact)
- `tests/unit/test_memory_v2_quality.py`
- `PROJECT_STATE.md`

### Constraints honored

- No new API, memory type, DB, router, Redis migration, or UI

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
