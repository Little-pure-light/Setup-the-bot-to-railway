# REDIS_AUDIT — 小宸光 Setup-the-bot-to-railway

| 項目 | 內容 |
|------|------|
| 文件版本 | 1.0 |
| 日期 | 2026-07-25 |
| 性質 | **僅診斷**（不修改程式、不部署、不新增套件） |
| 程式庫 | `Setup-the-bot-to-railway` @ 當前 `main`（參考 commit 含 `8eee450` 品質版） |
| 現場探測 | `GET https://ai2.dreamground.net/ready`（2026-07-25） |

**密鑰政策：** 本文不包含任何 Token、密碼或完整連線字串；URL 一律遮蔽。

---

## 1. 使用 Redis 的程式檔案、函式與用途

### 1.1 連線與抽象層

| 檔案 | 符號 | 用途 |
|------|------|------|
| `backend/redis_interface.py` | `RedisInterface` | 正式短期記憶接口；自動連真實 Redis 或降級 Mock |
| | `_auto_init_redis` | 讀 env、`from_url` / host+token、`ping` |
| | `_init_redis_mock` | 降級 `RedisMock` |
| | `store_short_term` | 寫 `conv:{id}:latest` + expire |
| | `load_recent_context` | 讀最新對話快照 |
| | `normalize_latest_payload` | 正規化 messages/summary/reflection |
| | `clear_conversation` | 刪最新對話 key |
| | `get_stats` | 狀態摘要 |
| `backend/redis_mock.py` | `RedisMock` | 程序內記憶體假 Redis（set/get/list/hash/keys/scan…） |
| | `get_redis_client` | Mock 單例（**RedisInterface 未使用此單例**，直接 `RedisMock()`） |

### 1.2 業務呼叫點

| 檔案 | 函式 / 位置 | Redis 操作 | 用途 |
|------|-------------|------------|------|
| `backend/chat_router.py` | 模組級 `redis_interface = RedisInterface()` | 初始化連線 | 全域共用實例 |
| | `get_reflection_storage()` | `RedisInterface()` **再建一個** | 反思儲存專用 |
| | `chat` 路徑 ~591–595 | `keys(upload:…*)` + `get` | 取上傳檔／Vision 暫存 |
| | `_build_memory_system` | 注入 `redis_interface` 進 MemorySystem | 短期對話快取 |
| `modules/memory_system.py` | `__init__` | 可選自建 `RedisInterface()` | 未注入時 |
| | `_cache_short_term` | `store_short_term` → set+expire | 存最新一輪 |
| | `get_recent_context` | `load_recent_context` → get | 讀最新一輪（若呼叫端使用） |
| `backend/modules/reflection_storage.py` | `_store_to_redis` | `lrange` + `lpush` + `ltrim` + `expire` | 反思列表快取 |
| | `_get_from_redis` | `lrange` | 讀反思快取 |
| `backend/file_upload.py` | 上傳／vision 路徑 | `setex` | `upload:{conv}:{filename}` 暫存（~2 天） |
| `backend/archive_conversation.py` | `get_conversation_from_redis` | `lrange` on `conversations:{id}` | 封存用對話列表（**舊 key 形態**） |
| | 檔案掃描 | `scan` + `get` | 收集 upload 鍵 |
| `backend/history_router.py` | 刪對話 | `clear_conversation` + `keys` + `delete` | 清短期與 upload |
| `backend/modules/graph_manager.py` | `_ensure_loaded` / `_persist` | `get` / `set` | 可選：`memory_graph:{user}:edges`；失敗回落檔案 |
| `backend/ai_kernel/adapters.py` | `FileContextAdapter` | `keys` + `get` | Kernel 路徑讀 upload |
| `backend/internal_night_growth_router.py` | `_build_manager` | `RedisInterface()` | 建 MemoryManager 時可掛 redis |
| `backend/memory_router.py` | 初始化 | `RedisInterface()` | 記憶相關路由 |
| `backend/health.py` | `readiness_payload` | **不連線** | 只看 env 是否設定 |
| `backend/healthcheck_router.py` | `/health/detailed` | **不連線** | 顯示 REDIS_URL 有無 |

### 1.3 測試

| 檔案 | 說明 |
|------|------|
| `tests/**` | 多處 `MagicMock` / `MockRedisInterface`，不連正式 Redis |

---

## 2. 讀取的環境變數

| 變數 | 誰讀 | 用途 | 備註 |
|------|------|------|------|
| `REDIS_URL` | `redis_interface._auto_init_redis`、`health.readiness` | 主要連線字串 | 若以 `redis://` 開頭會被**改寫成** `rediss://`（強制 SSL） |
| `REDIS_ENDPOINT` | `redis_interface` | 與 URL 同源備援；或 host 字串 | 非 `redis://`/`rediss://` 時與 Token 搭配 |
| `REDIS_TOKEN` | `redis_interface` | password / Upstash token | 搭配 endpoint host 模式 |
| `MEMORY_REDIS_TTL_SECONDS` | `RedisInterface.__init__` | `conv:*:latest` TTL | **預設 86400（24h）** |
| `REDIS_HOST` | **僅** `health.py` readiness | 判斷「有設定」→ configured | ⚠️ **RedisInterface 並不讀 REDIS_HOST**，與 health 語意不一致 |
| （文件提及）`REDIS_HOST` | `docs/ENVIRONMENT_VARIABLES.md` | 文件層 | 實作以 URL / ENDPOINT+TOKEN 為準 |

**未發現：** 程式內明確的 `REDIS_PORT` 環境變數讀取（host 模式寫死 `port=6379`）。

**遮蔽範例（形狀 only）：**

```text
REDIS_URL=rediss://default:****@****.upstash.io:****
REDIS_ENDPOINT=****.upstash.io
REDIS_TOKEN=********
```

---

## 3. 連線失敗時的降級與延遲

### 3.1 初始化（`RedisInterface._auto_init_redis`）

```text
1) REDIS_URL 或 REDIS_ENDPOINT 為 URL
   → redis.from_url(...) → ping()
   → 失敗：print 警告，進入下一步
2) REDIS_ENDPOINT(host) + REDIS_TOKEN
   → Redis(host, port=6379, password, ssl=True) → ping()
   → 失敗：print 警告
3) RedisMock() 記憶體模式
   → 成功：短期功能仍「可用」但僅單實例、不跨機器
```

- **無無限重試迴圈**；失敗即往下一個策略。  
- **無**顯式 `socket_timeout` / `socket_connect_timeout` 設定 → 使用 **redis-py 預設**（連線問題時可能阻塞至 TCP/SSL 逾時，常見數秒～十幾秒級，依網路與 client 版本）。  
- 降級後：`self.redis` 為 Mock，**不**再打外部。

### 3.2 業務路徑失敗

| 路徑 | 失敗行為 | 是否拖垮主對話 |
|------|----------|----------------|
| `store_short_term` | try/except → False / print | 否 |
| `load_recent_context` | try/except → None | 否 |
| `_cache_short_term` | 略過 | 否（Supabase 長期仍寫） |
| 上傳 setex | warning | 檔案仍可走 Supabase Storage 路徑（視實作） |
| chat 讀 upload keys | warning，無檔案上下文 | 否 |
| reflection Redis | redis_success=False，仍可寫 Supabase | 否 |
| graph redis | warning，回落 JSON 檔 | 否 |

### 3.3 現況重要結論

**目前 live `/ready` 的 `redis: unavailable` 並非「連線錯誤訊息」，而是「環境變數未設定」。**  
此時進程多半已在 **Mock 模式**（若程式啟動時也無 URL），聊天主路徑不會卡在外部 Redis；但會失去跨 replica / 重啟後的短期一致性。

---

## 4. 每次聊天請求大約呼叫 Redis 幾次

### 4.1 典型 `POST /api/chat`（無檔案、有背景反思、V1/V2 記憶寫入）

| 階段 | 操作 | 約計次數 |
|------|------|----------|
| 請求初：upload 檢索 | `KEYS upload:{conv}:*` + 可能 `GET` | **0–2**（無 upload 時 KEYS 仍 1 次） |
| 同步主路徑 | 通常**不再**讀 `conv:…:latest` 建 prompt（歷史主要靠 Supabase） | **0** |
| 存記憶（前景或背景任務） | `SET` + `EXPIRE` on `conv:{id}:latest` | **2** |
| 背景反思寫入 | `LRANGE` + `LPUSH` + `LTRIM` + `EXPIRE` on `reflections:{id}` | **0 或 4** |
| V2 Graph（若寫 typed 且 graph 掛 redis） | 可能 `GET`/`SET` graph key | **0–2** |

**粗估合計：**

| 情境 | 約計 Redis 命令數 |
|------|-------------------|
| 純文字聊天 + 記憶 + 反思 | **約 6–8** |
| 純文字、無反思寫入 | **約 3**（1 keys + 2 set/expire） |
| 含檔案上下文 | **+1 get**（keys 後） |
| Mock 模式 | 次數相同，但是記憶體內 O(1)/O(n keys) |

### 4.2 注意：`KEYS` 指令

`chat_router` / Kernel adapter / `history_router` 使用 **`keys(pattern)`**（非 SCAN）。  
在**真實 Redis** 上 `KEYS` 為 **O(N) 阻塞**，upload key 多時會放大延遲。Mock 上為記憶體掃描。

---

## 5. Timeout / 重複連線 / 每請求重建 / 無限重試

| 風險項 | 現況判定 |
|--------|----------|
| 過長 timeout | **未設定** socket timeout → 連線失敗時可能長時間阻塞（初始化時） |
| 無限重試 | **無**；init 失敗單次降級 |
| 每請求重建連線 | **否**（模組級單例為主）；但**多處各自 `RedisInterface()`** |
| 重複連線實例 | **是** — 至少：`chat_router`、`get_reflection_storage`、`file_upload`、`archive_conversation`、`history_router`、`memory_router`、`internal_night_growth`、`MemorySystem` 未注入時 等，**各建一個** |
| Mock 共享 | `RedisMock._storage` 為**類別級**共享，多實例仍共享資料；真實 Redis 則多 connection |
| 啟動連線成本 | 每個 `RedisInterface()` 在有 URL 時都會 `from_url` + `ping` 一次 |

**結論：** 無無限重試；主要結構風險是 **多實例初始化** + **無 timeout** + **KEYS 阻塞**。

---

## 6. Redis 存放哪些資料（快取 vs 不可遺失）

| Key 模式 | 寫入方 | TTL | 性質 | 遺失影響 |
|----------|--------|-----|------|----------|
| `conv:{conversation_id}:latest` | MemorySystem / RedisInterface | `MEMORY_REDIS_TTL_SECONDS`（預設 24h） | **快取**（最新一輪 + summary + reflection） | 低：長期在 Supabase |
| `reflections:{conversation_id}` | ReflectionStorage（list） | 86400，最多約 5 筆 | **快取** | 低：可回 Supabase / 再生成 |
| `upload:{conversation_id}:{filename}` | file_upload / vision | 172800（2 天） | **暫存快取** | 中：需重傳檔才有上下文 |
| `memory_graph:{user_id}:edges` | GraphManager（可選） | 未見 expire | **半持久快取**；主落點常為檔案 `MEMORY_GRAPH_FILE` | 中低：檔案可回落 |
| `conversations:{conversation_id}` | archive 讀取用 list | 不明（舊路徑） | **可疑舊格式** | 若只靠此封存則危險；主路徑封存偏好 Supabase |

**明確不在 Redis（預設）：**

- 長期對話 / embedding 列 → **Supabase**  
- 提醒 → **本地 JSON**（`data/reminders.json`）  
- Identity Charter → **檔案系統**  
- Token ledger → **JSONL 檔**

**判定：** Redis 在本專案定位為 **短期快取／暫存**，**不應**承載唯一真相資料。現況未設 URL 時，連跨進程一致性都沒有。

---

## 7. `/ready` 顯示 Redis unavailable 的實際含義

### 7.1 現場回應（已探測，無密）

```json
{
  "status": "degraded",
  "check": "readiness",
  "services": {
    "app": "ok",
    "openai_config": "configured",
    "supabase_config": "configured",
    "redis": "unavailable",
    "supabase": "config_only"
  },
  "notes": {
    "redis": "env_presence_only_not_ping"
  }
}
```

### 7.2 程式邏輯（`backend/health.py`）

```text
if REDIS_URL 或 REDIS_HOST 有非空值 → services.redis = "configured"
else → services.redis = "unavailable"
```

- **不做** `PING`  
- **沒有**「Connection refused / Timeout / NOAUTH」等錯誤字串回傳  
- `unavailable` = **環境變數未設定（或空白）**  
- 因此 **實際錯誤訊息：無**；語意是 *not configured*，不是 *connection failed*

### 7.3 與運行時行為的落差

| 層 | 含義 |
|----|------|
| `/ready` | 沒設定 `REDIS_URL`/`REDIS_HOST` → unavailable → 整體 **degraded** |
| 執行期 | 無 URL 時 `RedisInterface` → **Mock**，聊天仍可跑 |
| 若設了錯誤 URL | `/ready` 可能顯示 **configured**，但 init 失敗仍 Mock；**ready 會誤報健康** |

---

## 8. Railway 日誌：聊天各階段耗時

### 8.1 本診斷無法取得的內容

- 本環境 **Railway CLI 未連結專案**、無 Dashboard 日誌匯出。  
- **無法**從 Railway 抽出「某一次真實聊天」的 Redis / Supabase / Embedding / 記憶檢索 / LLM 毫秒數。

### 8.2 程式內既有計時能力（靜態分析）

| 階段 | 是否有結構化耗時 log |
|------|----------------------|
| Redis | **無** 專用 stage timer |
| Supabase | **無** 統一 stage timer |
| Embedding | **無**（`memory_system` / embedding create 無 elapsed log） |
| 記憶檢索 | **無** 統一 |
| LLM | 部分 usage／工具 `duration_ms`；Kernel 有 `tracing` stage |
| Tools | `duration_ms` 有 |

### 8.3 建議的「一次請求」耗時拆解方式（供你之後在 Railway 做，非本階段執行）

1. 開一筆測試 `conversation_id`，打 `POST /api/chat?stream=false`。  
2. Railway Logs 過濾 `request_id` / `conversation_id`。  
3. 暫時（未來實作）在下列點打 `perf_counter`：  
   - redis keys/get  
   - supabase history / insert  
   - embeddings.create  
   - recall / retrieve  
   - chat.completions  

**目前只能依架構推論延遲主因排序（見文末），不能假裝已有實測毫秒表。**

---

## 9. 修復方案（只提案，不執行）

### P0 — 設定與語意對齊

1. 在 Backend Railway 設定真實 `REDIS_URL`（或 `REDIS_ENDPOINT`+`REDIS_TOKEN`）。  
2. 修正 `/ready`：  
   - 區分 `not_configured` / `configured` / `ping_ok` / `ping_fail`；  
   - 可選輕量 `PING`（短 timeout，例如 200–500ms）。  
3. 讓 `REDIS_HOST` 要嘛實作支援，要嘛文件與 health 改為與程式一致。

### P1 — 連線健壯性

1. `redis.from_url(..., socket_connect_timeout=…, socket_timeout=…)` 明確上限。  
2. **單一** Redis 連線工廠（全域單例），禁止路由各建 `RedisInterface()`。  
3. 禁止啟動時無 timeout 的長阻塞 `ping` 拖垮 worker。

### P2 — 熱路徑效能

1. `keys(upload:…*)` 改 **SCAN** 或固定 key / index set。  
2. 無 upload 時可跳過 redis 掃描（flag 或請求 metadata）。  
3. Mock 與真實路徑分開 metrics。

### P3 — 資料一致性

1. 確認 `conversations:{id}` list 是否仍寫入；若否，archive 僅依賴 Supabase。  
2. Graph 以檔案或 Supabase 為 source of truth，Redis 僅 cache。  
3. 多 replica 時 **必須** 真實 Redis，禁止依賴 Mock 共享幻覺。

### P4 — 可觀測性

1. 聊天管線 stage timing（Redis/SB/Embed/Recall/LLM）寫入 log（無 secret）。  
2. `/ready` 與 `/health/detailed` 回傳 redis mode：`real|mock|none`。

---

## 10. 密鑰與 URL

- 全文已遮蔽。  
- 診斷過程未寫入任何完整 `REDIS_URL` / Token 至檔案。

---

## 最可能的變慢原因（依可能性排序）

> 針對「現況 live + 程式結構」綜合判斷；**非** Railway 單次請求實測。

| 順位 | 原因 | 說明 |
|------|------|------|
| **1** | **LLM 生成與串流** | 主路徑成本最高；與 Redis 無關時仍佔總延遲主體 |
| **2** | **OpenAI Embedding（存記憶）** | `save_memory` 每次對話 embedding + Supabase 讀寫 |
| **3** | **Supabase 讀寫／向量召回** | 歷史與 memories 表；網路 RTT |
| **4** | **Redis 未配置 → Mock 錯覺** | 非直接變慢，但多 replica 狀態不一致、重啟丟 upload/短期上下文，造成「重查 Supabase／重傳檔」間接變慢 |
| **5** | **初始化時 Redis URL 錯誤且無 timeout** | 若誤設 URL，worker 啟動或首次 `RedisInterface()` 可能卡住數秒 |
| **6** | **真實 Redis 上使用 KEYS** | upload 多時阻塞 |
| **7** | **多實例 RedisInterface + 重複 ping** | 冷啟動／新 worker 放大 |
| **8** | **背景反思／工具** | 通常不阻塞首包，但影響總資源 |

**與 `/ready` redis unavailable 的關係：**  
它**本身不是**「Redis 連線超時拖慢每次聊天」的證明；它只證明 **沒設 REDIS_URL/HOST**。  
現況更像：**短期層在 Mock，主延遲在 LLM + Embedding + Supabase。**

---

## Redis 搬到 Railway 會動到什麼

### 環境變數（建議）

| 動作 | 變數 |
|------|------|
| 新增／設定 | `REDIS_URL=redis://…` 或 Railway Redis 外掛提供的 URL（若需 TLS 用 `rediss://`） |
| 可選 | `MEMORY_REDIS_TTL_SECONDS` |
| 對齊文件 | 若用 host 模式：`REDIS_ENDPOINT` + `REDIS_TOKEN`；或實作 `REDIS_HOST`/`REDIS_PORT` |
| 不必為搬移而改 | `API_SECRET`、`OPENAI_*`、`SUPABASE_*`（除非連線字串誤寫進同一變數） |

**注意現有行為：** `redis://` 會被自動改成 `rediss://`。若 Railway 內網 Redis **不支援 TLS**，此 AUTO-FIX 會導致連線失敗 → Mock。搬移時必須驗證。

### 可能修改的檔案（建議清單，**尚未改**）

| 檔案 | 原因 |
|------|------|
| `backend/redis_interface.py` | timeout、單例、TLS 策略可配置、健康 ping |
| `backend/health.py` | ready 狀態語意、可選 ping |
| `backend/chat_router.py` | 共用單例、KEYS→SCAN、可選跳過 upload 掃描 |
| `backend/ai_kernel/adapters.py` | 同上 keys |
| `backend/file_upload.py` / `history_router.py` / `archive_conversation.py` | 共用 client |
| `backend/modules/reflection_storage.py` | 共用 client |
| `docs/ENVIRONMENT_VARIABLES.md` | 變數說明與 TLS 注意 |
| `docs/BACKUP.md` / 架構狀態文件 | 運維現況 |

**通常不必改：** LLM、Supabase schema、前端。

---

## 搬移風險與回滾

### 風險

| 風險 | 等級 | 說明 |
|------|------|------|
| TLS AUTO-FIX 與內網 Redis 不合 | 高 | 連不上 → 靜默 Mock |
| 多 replica 切換瞬間資料 | 中 | Mock→Real 後舊記憶體資料不遷移（本就非持久） |
| KEYS 在生產 keyspace | 中 | 流量大時延遲尖峰 |
| 誤把 Redis 當唯一存檔 | 高 | 違反現架構；upload/短期會丟 |
| 密碼／URL 進 log | 中 | 現有 print 可能含 endpoint 字串，需脫敏 |

### 回滾

1. Railway 移除或清空 `REDIS_URL`（及 ENDPOINT/TOKEN）。  
2. 重啟服務 → 自動回 **Mock**。  
3. `/ready` 再變 `redis: unavailable` / degraded（與今日類似）。  
4. **長期記憶不受影響**（Supabase）。  
5. 使用者可能需 **重傳檔案**（upload 暫存消失）。  
6. 程式回滾：若有改 `redis_interface` TLS/單例，git revert 該 commit 即可。

---

## 附錄 A — 初始化與聊天 Redis 流程（文字）

```text
App import chat_router
  → RedisInterface()
      → (有 URL?) ping → real : mock

POST /api/chat
  → keys(upload:conv:*) [+ get]
  → … LLM / Supabase / embedding …
  → save_memory → set+expire conv:…:latest
  → (bg) reflection → lpush/ltrim/expire reflections:…
```

## 附錄 B — 診斷限制聲明

| 項目 | 狀態 |
|------|------|
| 靜態程式碼盤點 | 完成 |
| Live `/ready` | 完成 |
| Railway 單次請求 flame/latency | **未取得**（無日誌權限） |
| 真實 Redis PING 延遲 | **未測**（現況無 URL） |
| 程式修改 / 部署 | **未執行**（依需求） |

---

*本文件為診斷交付物。若進入修復階段，請另開任務並逐項核准 P0–P4。*
