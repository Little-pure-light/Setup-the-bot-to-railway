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

---

# Task009-006 — 加密遠端備份 workflow（scaffolding；正式啟用＝Task009-007）

## 什麼被建立
- `.github/workflows/task009-backup.yml`：排程 **每日 03:17 Asia/Taipei（19:17 UTC）** + 手動 `workflow_dispatch`。
- `scripts/backup/task009_remote_backup.ps1`：row-count(**固定四表、不可縮減**)→pg_dump→manifest+SHA-256→驗證→打包→**age 公鑰加密**→上傳**私有 Cloudflare R2**(含 sha256 object metadata)→**HEAD size+checksum 驗證**→精確清理。fail-closed；**絕不上傳明文**；不刪遠端物件（30 天保留＝R2 lifecycle，於 007 設定）。
- CI job `task009-remote-backup-safety`：以假工具真跑正負向測試（含真實 manifest 竄改 / dump 破壞由正式 checker 攔截、外部工具輸出去敏、cleanup 越界安全）。

## 第二輪 Push 前補修（對應 CODEX_009_006_ROUND2）
- **固定四表、不可縮減**：row-count 集合為程式常數 `public.xiaochenguang_memories / public.xiaochenguang_reflections / public.emotional_states / public.user_preferences`；已移除呼叫端可縮減的 `-RowCountTables` production 輸入；subset/unknown/duplicate 皆於**任何 SQL 查詢前** fail-closed。
- **restore_drill 契約同步**：`task009_restore_drill.ps1` 的 `source_row_counts` allowlist 同步為上述四表（新增 `public.xiaochenguang_reflections`），確保注入的 `source_contract.source_row_counts` 與還原驗證契約完全一致（Phase A safety 測試同步更新）。
- **真實負向驗證**：測試以真實 `task009_backup.ps1` 產物 + 真實 `task009_manifest_check.ps1`，實際竄改 manifest sha256、實際破壞 dump bytes，兩者都必須失敗（非僅替代 checker / 環境變數模擬）。
- **外部工具輸出去敏**：Phase A / psql / age / S3 client 的 stdout/stderr 一律捕捉不外流；失敗只回報**階段名 + exit code + 去敏錯誤類別**，不原樣印出 endpoint/bucket/DB host/name/user/secret/project ref；測試以假敏感字串驗證 log 不含。
- **決定性 S3 client**：workflow 以官方 installer **固定版本**（`AWSCLI_VERSION`，pinned）安裝並驗證 AWS CLI v2，不依賴 runner 映像預裝。
- **cleanup 越界安全**：抽出 `Remove-RunDirSafe`（越界一律拒刪）；測試證明 sibling 與 runner temp 外部檔案不會被刪除、僅移除本 run 目錄。
- **CI 狀態：尚未實跑（NOT_RUN）**。本輪沙箱無 pwsh/pg_dump/pg_restore/psql/age/aws，完整 PowerShell 測試由 CI 於 Push 後執行；本地僅做靜態檢查（YAML 解析、`git diff --check`、secret scan、括號/結構核對）。**不得將靜態檢查當作 CI PASS。**

## 目前為 INERT（未啟用）
workflow 只在 **default branch** 的 schedule/手動觸發；正式 backup 需 repo variable **`TASK009_BACKUP_ENABLED=true`**（見下方啟用矩陣）。在 Task009-007B 設定 Environment secrets/variables 前，排程不會執行正式備份、不會失敗、不碰正式服務。**PR 不觸發此 workflow。**

## 007A 啟用安全模型（activation gate）
本 workflow 綁定專用 **GitHub Environment `task009-backup`**（Environment secrets 由操作者於 007B 直接於平台輸入，**不進 repo/log/聊天**）。run/skip 與 dry-run/live 判定由 `scripts/backup/task009_workflow_gate.sh` 決定（fail-closed），矩陣如下：

| 觸發 | `dry_run` 輸入 | `TASK009_BACKUP_ENABLED` | 結果 |
|---|---|---|---|
| 手動 workflow_dispatch | `true`（預設） | 任意（含未設/false） | **RUN dry-run**：不讀 secrets、不連 DB/R2、不查詢、不加密、不上傳 |
| 手動 workflow_dispatch | `false` | 未設 / `false` | **SKIP** |
| 手動 workflow_dispatch | `false` | `true` | **RUN live**（正式備份） |
| schedule | —（排程無輸入） | 未設 / `false` | **SKIP** |
| schedule | —（永不 dry-run） | `true` | **RUN live**（正式備份） |

要點：**schedule 永遠不會 dry-run**，只會在 enabled=true 時跑正式備份；**手動 dry-run 即使 disabled 也能安全執行**（零連線、零上傳），供 007B 啟用前驗證。gate 的四種必測矩陣由 CI job `task009-workflow-gate`（`tests/workflow/task009_gate_matrix_tests.sh`）驗證。

## 安全操作順序（007A → 007B）
1. **007A（本 PR，repository only）**：加入 Environment 綁定、`dry_run` 輸入、gate 與測試；建立未合併 Draft PR＋CI。**不建立** Environment/secrets/variables/R2/age 私鑰，**不連正式**。
2. **007B（另批，經 Codex 驗收 + 一竅哥批准合併 007A 後才做）**：見「Task009-007B 啟用前需逐項批准建立」。啟用前務必先 **手動 dry-run（enabled 尚未 true）** 驗證零連線/零上傳，再設 `TASK009_BACKUP_ENABLED=true`，於避開 03:17 的受控時間手動 `dry_run=false` 執行**一次**正式備份，驗證 job SUCCESS、R2 僅有 `.age`＋去敏 manifest/checksum、HEAD size/metadata checksum 一致；不下載、不解密、不 restore（隔離還原屬 Task009-008）。

## Task009-007B 啟用前需逐項批准建立（007A 本批不建立）
- GitHub secrets：`TASK009_PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD`（Supabase shared pooler session mode，供 psql row-count）、`TASK009_PG_DIRECT_HOST`（Supabase 直連主機 `db.<project-ref>.supabase.co`，供 pg_dump 繞過 pgBouncer）、`TASK009_R2_ACCESS_KEY_ID/TASK009_R2_SECRET_ACCESS_KEY`（**僅限該 bucket 的 R/W token**）。
- GitHub variables：`TASK009_AGE_RECIPIENT`（age **公鑰**，非秘密）、`TASK009_R2_BUCKET`、`TASK009_R2_ENDPOINT`、`TASK009_PG_DIRECT_PORT`（Supabase 直連埠，通常 `5432`）、`TASK009_BACKUP_ENABLED=true`。
- **pg_dump 直連說明**：Supabase shared pooler（pgBouncer session mode）不支援 pg_dump 所需的 binary protocol（`--format=custom`）。`TASK009_PG_DIRECT_HOST`（secret）＋`TASK009_PG_DIRECT_PORT`（variable，預設 5432）會被注入為 `PG_DUMP_HOST`/`PG_DUMP_PORT`，task009_backup.ps1 在呼叫 pg_dump 時使用直連，psql row-count 仍使用 pooler。若未設定 `PG_DUMP_HOST`，pg_dump 退回 `PGHOST/PGPORT`（向後相容）。
- Cloudflare R2：私有專用 bucket（不綁 public domain）、30 天 lifecycle 保留。
- age **私鑰**：一竅哥離線保存兩份，**絕不**進 GitHub/Railway/repo/協作資料夾。
- GitHub Actions **失敗 email 通知**已開啟。

## Public repo 排程注意
Public repository 於 repo **60 天無活動**可能停用 scheduled workflow。請保留手動「Run workflow」按鈕，並**每月**檢查排程是否仍啟用；停用時以 `workflow_dispatch` 手動執行並重新啟用排程。

## 本 workflow **未涵蓋**的 DR 資產（不得冒充完整 DR）
- Supabase **Auth（10 使用者）**：未涵蓋（不在 public dump）。
- Supabase **Storage**（目前 0 bucket/0 物件）：目前無資料；未來啟用需另納管。
- **Pinecone**（1 index、`__default__` namespace、209 records、1536-d cosine）：與 Supabase reflections(36) 數量不一致，**重建性未證**（`PINECONE_REBUILDABILITY_NOT_PROVEN`）→ 需獨立 export/rebuild policy。
- Railway backend **reminders / identity / token ledger**：backend 無 volume＝ephemeral，重部署遺失；reminders/identity 為唯一真相且無重建來源。
- **Redis volume**：AOF/RDB、snapshot/實際還原能力未證。

> 以上皆為後續 DR 工作；Task009-006 僅涵蓋 Supabase `public` PostgreSQL 的加密遠端備份 scaffolding，**非**完整 DR、**非**正式啟用。
