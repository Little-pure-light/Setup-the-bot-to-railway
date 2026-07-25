# REDIS_IMPLEMENTATION_REPORT

**本任務必須遵守《小宸光 Agent 工程執行與驗收通用規範 v1.0》。**  
執行書：`小宸光_Redis遷移與效能診斷_Agent執行書_v1.0`  
分支：`fix/redis-railway-safe-observability`  
日期：2026-07-25

---

## 1. 本次做了什麼

### 第一階段（程式）

- 修正 **不強制** `redis://` → `rediss://`（TLS 僅 `rediss://` 或 `REDIS_SSL=true`）
- 連線／讀取 **明確 timeout**（預設 2s，可 env 調）
- **單一共用** `get_shared_redis_interface()`
- 模式 **`real` / `mock` / `none`**，失敗不裝成功
- `/ready` **短 PING**，狀態：`not_configured` | `mock` | `ping_ok` | `ping_fail`
- 熱路徑 **KEYS → SCAN**（`scan_keys`）
- 日誌只記錯誤類型與遮蔽 host，不記密碼

### 第二階段（可觀測性）

- 新增 `backend/request_timing.py`
- 聊天路徑記錄：`memory_recall`、`supabase_history`、`redis_upload_read`、`memory_save`、total_ms
- 環境變數 `REQUEST_TIMING_ENABLED`（預設 true）

### 未由 Agent 執行（需你在 Railway）

- 新增 Redis Service、掛 `REDIS_URL` Service Reference
- Production 上 10+ 次實測延遲表（無 Railway Redis 前僅能本地 mock 計時）

---

## 2. 修改檔案清單與理由

| 檔案 | 理由 |
|------|------|
| `backend/redis_interface.py` | TLS、timeout、singleton、mode、scan、ready helper |
| `backend/health.py` | 真實 short ping 狀態 |
| `backend/request_timing.py` | 階段耗時 |
| `backend/chat_router.py` | 共用 client、SCAN、計時掛點 |
| `backend/ai_kernel/adapters.py` | SCAN |
| `backend/history_router.py` | 共用 + SCAN |
| `backend/file_upload.py` | 共用 client |
| `backend/archive_conversation.py` | 共用 client |
| `backend/memory_router.py` | 共用 client |
| `backend/internal_night_growth_router.py` | 共用 client |
| `modules/memory_system.py` | 共用 client |
| `tests/unit/test_redis_safety.py` | real/mock/failure 類測試 |
| `docs/REDIS_IMPLEMENTATION_REPORT.md` | 本報告 |
| `docs/ENVIRONMENT_VARIABLES.md` |（若已更新）Redis 變數 |

未改：Memory V2 核心邏輯、Night Growth 決策、人格、Supabase schema、API 契約。

---

## 3. Railway 需要設定的變數（值遮蔽）

| 變數 | 說明 |
|------|------|
| `REDIS_URL` | Railway Redis 私有網路 URL（**優先**；`redis://` 內網勿強改 TLS） |
| 可選 `REDIS_CONNECT_TIMEOUT_SECONDS` | 預設 `2.0` |
| 可選 `REDIS_SOCKET_TIMEOUT_SECONDS` | 預設 `2.0` |
| 可選 `REDIS_SSL` | `true`/`false` 覆蓋 TLS |
| 可選 `MEMORY_REDIS_TTL_SECONDS` | 預設 `86400` |
| 可選 `REQUEST_TIMING_ENABLED` | 預設 `true` |

**不要**把密碼寫進 Git。用 Railway **Service Reference** 注入 `REDIS_URL`。

---

## 4. 測試指令與結果

```bash
pytest tests/unit/test_redis_safety.py -q
pytest tests/ -q
```

（執行時以本機結果為準，見 Agent 回報「實際測試」。）

---

## 5. 第一階段驗收表

| 條件 | 狀態 |
|------|------|
| 程式支援 ping_ok / mock / ping_fail / not_configured | **代碼完成** |
| 啟動可 log redis_mode | **完成** |
| Redis 暫停可降級且 ready 不裝綠 | **邏輯完成**（待 Railway 實測） |
| conv:latest 寫入 + TTL | **mock 測試**；real 待 URL |
| KEYS 熱路徑改 SCAN | **完成** |
| 自動測試 + redis 三類測試 | **見 pytest** |
| Production `/ready` 已是 ping_ok | **待你掛 REDIS_URL 並部署本分支** |

---

## 6. 第二階段效能報告

### 本地／未掛 Redis 時

- 計時程式已就緒；**尚無** Production 10 次 + 3 次記憶召回的實測統計表。  
- 原因：執行書要求比較 Redis 啟用前後，需你部署後從 log 收集 `chat_timing` 行。

### 收集方式（部署後）

1. 連續 10 次純文字 `/api/chat?stream=false`  
2. 3 次含既有記憶召回  
3. 從 log 抓 `chat_timing` / `⏱ chat_timing`  
4. 計算各 stage 平均／中位／最大  

### 在有實測前不得宣稱

「Redis 是唯一變慢原因」——與執行書一致。

---

## 7. 回滾

1. 移除 Backend `REDIS_URL` → 重部署 → **mock**  
2. `git revert` 本分支 commit 或切回合併前 commit  
3. Supabase 長期記憶不受影響  
4. 重測聊天 + `/ready`

---

## 8. 已知限制

- Railway Redis 服務本身需人工建立  
- host+token 路徑預設偏 Upstash SSL；Railway 內網請用 **REDIS_URL=redis://…**  
- 串流路徑的 first_token_ms 尚未全掛（非串流 complete 已有）  
- archive 舊 key `conversations:{id}` 未在本任務清理  

---

*文件結束*
