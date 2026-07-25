# 小宸光 V2 — 正式版架構與部署狀態

| 項目 | 內容 |
|------|------|
| 文件版本 | 1.0 |
| 日期 | 2026-07-25 |
| 程式庫 | `Little-pure-light/Setup-the-bot-to-railway` |
| 分支 | `main` |
| 已部署 commit | `791506dd64500677ed6a264b893e259e5371195d`（短：`791506d`） |
| 文件性質 | **現況快照**（架構 + 部署 + 驗證 + 邊界），非未來路線圖全文 |

---
# 專案目前狀態（給老闆看的）

目前版本：
V2

目前狀態：
🟢 穩定

目前部署：
Production

目前驗證：
全部完成

目前風險：
Redis 暫停
Identity 深度不足

目前唯一工作：

Memory 品質優化






## 1. 一句話定義

小宸光 V2 是在 **不破壞既有聊天 API** 的前提下，以 **Strangler Pattern + Feature Flag** 疊加的 **認知記憶層**：

- 對話仍可走 V1 conversation 連續性  
- 開啟 `MEMORY_V2_ENABLED` 後，額外具備 **Typed Memory、Embedding 檢索、Graph、Identity Charter、Night Growth 鞏固**  
- 反思／Token／FineTune 資料契約已統一，為後續成長與微調預留接口  

**它不是**「已具備人類痛覺／主觀意識」的存有；  
**它是**「時間斷層上可驗證的橋」——可版本、可回滾、可開關。

---

## 2. 系統全景

```text
┌─────────────────────────────────────────────────────────────┐
│  使用者接觸面                                                │
│  · Open WebUI  (open-webui-production-df5b.up.railway.app) │
│  · 既有前端 / API 客戶端                                      │
│  · OpenAI 相容客戶端                                          │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTPS + Bearer (API_SECRET)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  小宸光 Backend  (ai2.dreamground.net)                       │
│  FastAPI · git_commit 可見於 /health                         │
│                                                             │
│  /api/chat  ─────────┬── AI Kernel (可選 flag)               │
│  /v1/*      ─────────┤                                      │
│  /internal/night-growth/run  (內部 token)                   │
│                      │                                      │
│  ┌───────────────────▼───────────────────┐                  │
│  │ Memory 門面 (Strangler)                 │                  │
│  │ MEMORY_V2_ENABLED=false → V1 only     │                  │
│  │ MEMORY_V2_ENABLED=true  → V2 適配器    │                  │
│  └───────────────────┬───────────────────┘                  │
│                      ▼                                      │
│  MemoryManager · Classifier · Retrieval · Graph             │
│  Identity Charter · Semantic · Decision · Night Growth      │
│  Reflection Contract · Token Ledger · FineTune JSONL        │
└───────────┬─────────────────┬─────────────────┬─────────────┘
            │                 │                 │
            ▼                 ▼                 ▼
      Supabase           Redis(*)           OpenAI
   (長期記憶表)        (短期/快取)      (chat + embedding)
   (*) 現況 readiness: unavailable — 暫緩遷移，對話仍可依賴 Supabase
```

---

## 3. 邏輯分層（對齊七層／認知記憶）

| 層級 | 職責 | V2 對應模組 | 完成深度 |
|------|------|-------------|----------|
| 接觸／API | 請求調度、串流、OpenAI 相容 | `chat_router`, `openai_compat_router` | 肉（router 仍偏大） |
| Kernel（可選） | 規劃／工具／策略 | `backend/ai_kernel/*` | 既有；獨立 flag |
| 記憶心臟 V1 | conversation 連續 | `modules/memory_system.py` | 肉；始終可回退 |
| 記憶心臟 V2 | 分類／檢索／圖譜 | `memory_manager`, `classifier`, `retrieval`, `graph` | 肉（規則+向量） |
| 身份 | 版本化自我描述 | `identity_engine` (Charter) | 肉（FS 存；非多裝置 DB） |
| 語義／決策 | 抽象知識、可測規則 | `semantic_builder`, `decision_engine` | **規則版肉**（非 LLM 深層） |
| 夜間成長 | 鞏固、寫入、防雙跑 | `night_growth`, `night_growth_safety` | 肉（endpoint 驗證通過） |
| 基礎設施 | 契約／Token／JSONL | `reflection_contract`, `token_counter`, `finetune_dataset` | 肉 |
| 反思 | 背景反思 + status | `reflection_storage` + `reflection_status` | 半肉（預設 pending） |

---

## 4. 核心架構元件

### 4.1 Memory V2 管線（聊天時）

```text
User message
  → (optional) V1/V2 recall + format
  → LLM 回覆
  → save:
        V1 conversation 列（相容）
      + V2 typed 列（episodic/semantic/identity/…）
      + embedding（ready | failed | unavailable）
      + graph 關聯（memory_id only）
```

### 4.2 Night Growth v2 管線（鞏固時）

```text
Load turns
  → Reflection normalize
  → Semantic Builder
  → Decision Engine（規則、可測）
  → Identity update（門檻 / candidate）
  → Attention / Transformation
  → Graph edges
  → Archive
```

安全：

- 同 `user_id` + UTC 日：正式完成後 **不重跑**（`skipped_duplicate`）  
- `dry_run` **不佔**當日冪等  
- 檔案鎖防並行  
- **不**在多 replica 自動 `while true` 排程（`NIGHT_GROWTH_ENABLED` 預設 false）  

### 4.3 Identity Charter

結構化版本庫（非 silent overwrite）：

- `mission[]`, `boundaries[]`, `growth_history[]`, `previous_version_id`, `change_reason`, `confidence`  
- 未達門檻 → **candidate only**  
- `IDENTITY_UPDATE_MODE=candidate`（建議 Staging）  
- **不直接改寫 system prompt**（僅 `to_prompt_fragment` 供上下文）  

### 4.4 Retrieval

```text
Intent → Memory Type → Embedding cosine → Graph expand → Rank
```

排序權重：vector / type match / importance / recency / graph confidence。  
無向量時 **keyword fallback** 並標 `source`。  
**user_id 隔離**。

### 4.5 Graph

- 節點：真實 `memory_id` only（禁 `reflection`/`document` 等字串節點）  
- 關係白名單：`supports | updates | contradicts | causes | derived_from`  
- Edge：`confidence`, `created_at`, `created_by`, `metadata`  
- 工具：`python scripts/check_memory_graph_integrity.py`  

### 4.6 Reflection API 行為

`include_reflection=true` 時：

```json
{
  "reflection_status": "pending | completed | failed | unavailable",
  "reflection": { ... } | null
}
```

禁止用空物件假裝「已完成」。

---

## 5. 主要 API 表面

| 方法 | 路徑 | 說明 | 驗證狀態 |
|------|------|------|----------|
| GET | `/health` | liveness + `git_commit` | 通過 |
| GET | `/ready` | readiness（現況 degraded） | 通過（degraded） |
| POST | `/api/chat` | 主聊天（`user_message` 欄位） | 通過 |
| GET/POST | `/v1/models`, `/v1/chat/completions` | OpenAI 相容（Open WebUI） | 通過 |
| POST | `/internal/night-growth/run` | Night Growth 觸發 | 通過 |
| 其他 | `/api/history/*`, `/api/tools`, voice, auth… | 既有能力 | 未本階段全量重測 |

認證：

- `/api/*`、`/v1/*`：`Authorization: Bearer <API_SECRET>`（或有效 Supabase JWT）  
- `/internal/*`：`NIGHT_GROWTH_INTERNAL_TOKEN`（未設則回退 `API_SECRET`）  

---

## 6. 部署拓樸（現況）

| 角色 | URL / 位置 | 說明 |
|------|------------|------|
| **Backend（小宸光 API）** | `https://ai2.dreamground.net` | Memory V2 實際執行處；commit `791506d` |
| **Open WebUI** | `https://open-webui-production-df5b.up.railway.app` | 前端 UI（v0.10.2）；**不是** Memory 後端 |
| **GitHub** | `Little-pure-light/Setup-the-bot-to-railway` | `main @ 791506d` |
| **Supabase** | 專案配置在 Backend env | 長期記憶列 |
| **Redis** | 現況 unavailable | 規格暫緩遷移；不影響本輪核心驗收結論 |
| **OpenAI** | Backend env | Chat + `text-embedding-3-small` |

### 6.1 部署原則（已遵守）

- 不遷移 Redis 平台  
- 不大改 Production 資料來源契約  
- Night Growth 不以常駐 in-process scheduler 在多 replica 自動跑  
- Feature Flag 可回滾  

### 6.2 現況重要事實

| 事實 | 說明 |
|------|------|
| 程式已在 `ai2.dreamground.net` | `/health.git_commit` = `791506d` |
| Backend 已開 `MEMORY_V2_ENABLED=true` | 使用者確認設在 Backend；§9 對話路徑依 V2 行為驗證 |
| Open WebUI 連線 | 應指向 Backend origin + API Key = `API_SECRET` |
| 本地未提交的驗證報告／腳本 | 驗證報告與 `verify_memory_v2_staging.py` 可能僅在工作區，需另 commit 若要入庫 |

---

## 7. 環境變數地圖

### 7.1 記憶 V2 核心

| 變數 | 預設 | 現況建議 |
|------|------|----------|
| `MEMORY_V2_ENABLED` | `false` | Backend **已 true**（驗證環境） |
| `IDENTITY_UPDATE_MODE` | `candidate` | 建議維持 candidate |
| `IDENTITY_CONFIDENCE_THRESHOLD` | `0.6` | 可維持 |
| `IDENTITY_STORE_DIR` | `data/identity` | 容器磁碟；重部署可能需 volume 意識 |
| `MEMORY_GRAPH_FILE` | `data/memory_graph.json` | 同上 |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | 維持一致維度 |
| `TOKEN_LEDGER_ENABLED` | `true` | 可維持 |
| `TOKEN_LEDGER_PATH` | `data/token_ledger.jsonl` | — |
| `NIGHT_GROWTH_ENABLED` | `false` | **維持 false**（用 endpoint 觸發） |
| `NIGHT_GROWTH_INTERNAL_TOKEN` | 空→`API_SECRET` | 須與呼叫端一致（已修復並驗證） |
| `NIGHT_GROWTH_ENDPOINT_ENABLED` | `true` | 維持 |
| `NIGHT_GROWTH_STORE_DIR` | `data/night_growth` | 執行紀錄／鎖 |
| `REFLECTION_INCLUDE_STATUS` | `true` | 維持 |
| `REFLECTION_INCLUDE_WAIT_MS` | `0` | 0=立刻 pending |
| `APP_ENV` | 空 | 可標 `staging` / `production` |

### 7.2 既有必要（未改契約）

`OPENAI_API_KEY`, `SUPABASE_URL`, `SUPABASE_ANON_KEY|KEY`, `SUPABASE_MEMORIES_TABLE`, `API_SECRET`, `REDIS_URL|HOST`（可選）…

完整表見：`docs/ENVIRONMENT_VARIABLES.md`。

---

## 8. 資料落點

| 資料 | 儲存 | 備註 |
|------|------|------|
| Conversation（V1） | Supabase `xiaochenguang_memories`（`memory_type=conversation`） | 相容主軸 |
| Typed V2 記憶 | 同表不同 `memory_type` | embedding + document meta |
| Graph | `data/memory_graph.json`（可選 Redis key） | 按 user_id 分區 |
| Identity Charter | `data/identity/{user}/` | versions + candidates + history |
| Night Growth 執行紀錄 | `data/night_growth/{user}/` | day lock / exec json |
| Token ledger | `data/token_ledger.jsonl` | 與訊息正文分離 |
| Redis conv latest | `conv:{id}:latest` | 現況 Redis unavailable 時降級 |

---

## 9. 驗證狀態（§9 · 2026-07-25）

| 區塊 | 結果 |
|------|------|
| Health / commit | **PASS** |
| Auth 401 | **PASS** |
| `/api/chat` + `/v1` + stream | **PASS** |
| 姓名／偏好／情緒／知識／召回 | **PASS** |
| `reflection_status=pending` | **PASS** |
| Night Growth dry_run | **PASS** → `completed_dry_run` |
| Night Growth formal | **PASS** → saved 29, graph edges 10 |
| 同日冪等 | **PASS** → `skipped_duplicate` |
| 匿名 NG | **PASS** → 401 |
| Redis | **degraded** |
| Identity 正式升版（本批） | Soft（patches=0，資料條件） |

詳細：`docs/fix_stage_reports/Staging_Verification_Report_2026-07-25.md`  
腳本：`scripts/verify_memory_v2_staging.py`

---

## 10. 誠實邊界（肉 vs 骨架）

| 項目 | 判定 |
|------|------|
| Strangler + flag 回滾 | 肉 |
| Typed memory + embedding 狀態 | 肉 |
| 對話召回（姓名／偏好／代號） | 肉（已實測） |
| Graph memory_id + 防雙邊 | 肉（NG 寫入已見 edge ids） |
| Night Growth 安全 | 肉（已實測） |
| Identity Charter 版本／candidate | 肉（程式）；遠端升版需 reflection 條件 |
| Semantic / Decision | **規則版**，非 LLM 深層認知 |
| chat_router 瘦身 | 半完成 |
| Redis 高可用 | **未就緒** |
| 多裝置 Identity 同步 | 未做（FS） |
| Fine-tune 訓練 | 不做（僅 JSONL 匯出能力） |
| 「有痛的溫度」 | **限制之門外** — 不偽造 |

---

## 11. 回滾與開關

```text
MEMORY_V2_ENABLED=false
TOKEN_LEDGER_ENABLED=false
NIGHT_GROWTH_ENABLED=false
# 可選：NIGHT_GROWTH_ENDPOINT_ENABLED=false
```

效果：

- 聊天立刻回 V1 門面  
- 不刪 V1 conversation  
- Identity／Graph 檔案可保留但不介入主路徑  

---

## 12. 操作速查

### 健康

```bash
curl -s https://ai2.dreamground.net/health
curl -s https://ai2.dreamground.net/ready
```

### 聊天（注意欄位名）

```bash
curl -s -X POST "https://ai2.dreamground.net/api/chat?stream=false" \
  -H "Authorization: Bearer $API_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"user_message":"你好","conversation_id":"demo","user_id":"demo_user"}'
```

### Night Growth

```bash
curl -s -X POST "https://ai2.dreamground.net/internal/night-growth/run" \
  -H "Authorization: Bearer $NIGHT_GROWTH_INTERNAL_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"demo_user","dry_run":true,"force":false}'
```

### 本地測試

```bash
python -m pytest tests/ -q
python scripts/check_memory_graph_integrity.py
```

---

## 13. 相關文件索引

| 文件 | 內容 |
|------|------|
| `docs/MEMORY_SYSTEM_V2.md` | V2 骨架說明 |
| `docs/MEMORY_V2_PHASE2.md` | Phase2 元件 |
| `docs/MEMORY_V2_FIX_STAGE.md` | Fix／Staging 階段 |
| `docs/INFRASTRUCTURE_PHASE.md` | Reflection／Token／JSONL |
| `docs/MIGRATION_NOTES_INFRA_MEMORY_V2.md` | 遷移／回滾 |
| `docs/ENVIRONMENT_VARIABLES.md` | 環境變數總表 |
| `docs/OPENWEBUI.md` | WebUI 連線 |
| `docs/fix_stage_reports/*` | 架構變更與各子報告 |
| `docs/fix_stage_reports/Staging_Verification_Report_2026-07-25.md` | 實測清單 |

任務書（just_for_Grok）：

- `Infrastructure_Phase_Agent_Execution_Specification.md`  
- `Memory_V2_Phase2_Agent_Execution_Specification.md`  
- `Memory_V2_Fix_Staging_Deployment_Test_Agent_Execution_Specification.md`  

---

## 14. 建議的下一步（非本文件範圍的決策）

1. **Redis**：補上 `REDIS_URL` 或接受 degraded 並文件化影響面  
2. **Identity volume**：若 Railway 無持久碟，Charter／Graph JSON 需評估掛載或改存 Supabase  
3. **API_SECRET 輪替**：曾在對話中出現，建議輪替  
4. **Production 策略**：是否長期維持 `MEMORY_V2_ENABLED=true` 於現網，或拆 Staging 服務  
5. **入庫**：將驗證報告與 `verify_memory_v2_staging.py` commit／push（若尚未）  

---

## 15. 狀態印章

```text
架構：Memory V2 + Infra Contract + Fix-stage Safety  已落地
部署：ai2.dreamground.net @ 791506d                 已對齊
驗證：§9 聊天／記憶／Night Growth                     已通過
已知降級：Redis unavailable
認知深度：規則 + 向量 + 版本化身份（非主觀感受）
回滾：MEMORY_V2_ENABLED=false 可用
```

**結論：**  
小宸光 V2 目前是 **可開關、可驗證、可鞏固的認知記憶正式工程版**；  
已在現網 Backend 以 flag 開啟並通過 Staging 級對話與 Night Growth 驗證。  
下階段應聚焦 **基礎設施韌性（Redis／持久化）** 與 **認知深度（非僅規則）**，而非再堆未驗證的模組數量。

## 下一步（唯一）

目前禁止新增新功能。

下一階段：

Memory Quality Improvement

目標：

- 提升記憶品質
- 提升 Retrieval
- 提升 Reflection
- 提升 Identity
