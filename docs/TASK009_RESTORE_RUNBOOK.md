# Task009 — 還原 Runbook（Phase A 文件；正式演練需 Phase B 批准）

> 目的：從 `task009_backup.ps1` 產生的備份，於**隔離（非正式）**環境還原並驗證。
> 嚴禁對正式資料庫執行 restore（正式啟用與正式演練屬 Phase B，需獨立批准）。
> 所有連線秘密僅來自環境變數；本文件不含任何密碼、token 或完整連線字串。

## 0A. 災難復原資產清單（Phase 狀態）
| 資產 | 備份方式/可重建方式 | 本 Phase 狀態 | Phase B Gate |
|------|---------------------|---------------|--------------|
| PostgreSQL schema/data | `task009_backup.ps1` + checksum manifest | IMPLEMENTED | 啟用正式排程與加密保存後才算正式有效 |
| Redis 必要持久卷（若使用 AOF/RDB） | 平台層快照或受控匯出（依部署型態） | DEFERRED_TO_PHASE_B | 定義平台快照頻率與復原流程 |
| Pinecone metadata | 以可重建索引清單/namespace 清單維護，必要時重建 | DEFERRED_TO_PHASE_B | 建立正式 export/rebuild runbook |
| Repository version | git commit / tag / release artifact | IMPLEMENTED | 發布清單與回滾點綁定 |
| Supabase Storage/Auth 相依 | 平台原生機制 + 應用層可重建清單 | DEFERRED_TO_PHASE_B | 明確化 Storage/Auth 災難步驟 |

備註：Phase A 僅完成 PostgreSQL 倉庫層工具與隔離演練契約，其他資產已明確標記延後，不可宣稱已定版完成。

## 1. 名詞
- 備份來源（正式，唯讀匯出）：`PG*` 環境變數。
- 還原目標（隔離）：`RESTORE_PG*` 環境變數（必須與來源不同）。

## 2. 前置條件
1. 已安裝 PostgreSQL 客戶端（`pg_dump` / `pg_restore`；可用 `PG_DUMP_PATH` / `PG_RESTORE_PATH` 指定）。
2. 已有一份通過驗證的備份目錄（含 `manifest.json` 與 schema/data dump）。
3. 隔離目標資料庫存在且**非正式**（本機 Docker/測試專案），連線只放 `RESTORE_PG*`。
4. 授權旗標：`RESTORE_ALLOW_ISOLATED=1`，且執行時帶 `-ConfirmIsolated`。
5. `psql` 可用於還原後 SELECT-only 契約驗證（可用 `PSQL_PATH` 指定）。
6. 還原目標若非 localhost，必須在 `RESTORE_ALLOWED_HOSTS` 精確 allowlist 中。

## 3. 還原前驗證
```powershell
pwsh scripts/backup/task009_manifest_check.ps1 -BackupDir <備份目錄>
# 須見 TASK009_MANIFEST_CHECK_PASS（dry-run 備份會 SKIPPED）
```
若雜湊/大小不符 → 停止，改用其他備份。

## 4. 隔離還原（先 dry-run，再實還原）
```powershell
# 3.1 先 dry-run（預設）：只列步驟，不連線
pwsh scripts/backup/task009_restore_drill.ps1 -BackupDir <備份目錄> -ConfirmIsolated

# 3.2 通過所有隔離防呆後，才實際還原到隔離目標
#     先在你的 shell 設定授權旗標與隔離目標連線環境變數（值勿寫入任何檔案/紀錄）：
#       RESTORE_ALLOW_ISOLATED=1
#       RESTORE_PGHOST / RESTORE_PGPORT / RESTORE_PGDATABASE / RESTORE_PGUSER / RESTORE_PGPASSWORD
#     （皆為隔離目標，且必須與備份來源 PG* 不同）
pwsh scripts/backup/task009_restore_drill.ps1 -BackupDir <備份目錄> -ConfirmIsolated -DryRun:$false
```
防呆（腳本強制）：
- 缺 `-ConfirmIsolated` 或缺 `RESTORE_ALLOW_ISOLATED=1` 一律拒絕。
- 非 localhost 目標必須命中 `RESTORE_ALLOWED_HOSTS` 精確 allowlist。
- 目標命中 `*.supabase.co`、`*.supabase.com` 或 pooler 一律拒絕。
- source/target 若 `host+port+database` 相同一律拒絕。
- 非 dry-run 缺 dump、缺 restore 連線必填值或 manifest 驗證失敗一律 exit 1。

## 5. 還原順序
1. schema（`--clean --if-exists --no-owner --no-privileges`）
2. data（`--data-only --no-owner --no-privileges`）

## 6. 驗證點（還原後於隔離目標執行 SELECT-only）
| 檢查 | 期望 |
|------|------|
| `xiaochenguang_memories` 可查、row_count 合理 | > 0 或與來源快照相符 |
| `emotional_states` / `user_preferences` 可查 | 表存在、可讀 |
| `memory_type='conversation'` 具 owner 欄位（user_id/ai_id） | 欄位存在（Task006 契約） |
| `pgvector` 擴展與 `embedding` 欄位存在 | 存在 |
記錄實際 row_count 與檢查結果到演練紀錄模板。

注意：不得假設只 dump `public` 就能在空白 DB 自動重建 extension；`vector` extension 應明確驗證存在，否則判失敗。

## 7. 失敗回滾
- 隔離還原失敗 → 直接丟棄隔離目標（drop/重建隔離 DB），不影響正式；記錄失敗原因（去敏）。
- **不對正式資料庫做任何 restore/DDL/DML**。

## 8. RPO/RTO（提案，非啟用）
見 `CLAUDE_009_001_BACKUP_SCOPE.md`。Phase A 僅提出；正式目標值與排程於 Phase B 批准。

## 9. 安全與營運控制（Phase B Gate）

以下在 Phase A 僅定義，尚未啟用，需於 Phase B 驗證後才可宣告正式達成：
- 備份檔 encryption-at-rest
- 備份目的地 ACL 與最小權限
- 備份失敗通知（告警通道、值班責任人）
- 秘密管理與輪替流程（不得落地明文）
- 緊急步驟與升級通報路徑

## 10. 去敏規範
紀錄與輸出不得含密碼、token、完整連線字串、完整 user/chat/conversation id；只留遮罩或計數。
