# Task009 隔離還原演練紀錄（模板）

- 日期／時間（UTC）：
- 執行者：
- 環境：ISOLATED（非正式）  ← 僅允許此值
- 備份來源標記（environment_label）：
- 備份目錄（去敏，尾碼）：…
- git_commit_short（來自 manifest）：

## 前置
- [ ] manifest_check PASS（或 dry-run SKIPPED）
- [ ] 隔離防呆全通過（-ConfirmIsolated、RESTORE_ALLOW_ISOLATED=1、目標≠來源、未命中正式標記）

## 還原
| 步驟 | 命令（去敏） | 退出碼 | 結果 |
|------|--------------|--------|------|
| schema restore | pg_restore --clean … | | |
| data restore | pg_restore --data-only … | | |

## 驗證點（SELECT-only，記 row_count / 布林）
| 檢查 | 期望 | 實際 | PASS/FAIL |
|------|------|------|-----------|
| xiaochenguang_memories row_count | >0 | | |
| emotional_states 可讀 | 是 | | |
| user_preferences 可讀 | 是 | | |
| owner 欄位(user_id/ai_id) 存在 | 是 | | |
| pgvector/embedding 存在 | 是 | | |

## 結果
- 總結：PASS / FAIL
- 失敗原因（去敏）：
- 隔離目標處置：已丟棄 / 保留供分析
- 備註：不含任何密碼/token/完整連線字串/完整 id
