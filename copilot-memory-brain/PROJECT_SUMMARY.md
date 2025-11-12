# Copilot Memory Brain - 專案總結

## 📌 專案概述

**Copilot Memory Brain** 是小宸光 AI 系統的子專案，為 VS Code Copilot 提供記憶存取能力，共享小宸光的完整記憶庫與反思系統。

**完成日期**: 2025-11-12  
**Architect 審查**: ✅ 通過  
**部署狀態**: 準備就緒

---

## 🏗️ 系統架構

### 後端服務 (FastAPI)
- **端口**: 8080
- **啟動命令**: `cd copilot-memory-brain/backend && python main.py`
- **健康檢查**: `GET /health`

### 核心 API 端點

#### 1. `/api/ask_copilot` (POST)
**主要功能**: VS Code Copilot 記憶查詢與生成
```json
{
  "prompt": "用戶問題",
  "conversation_id": "會話ID",
  "user_id": "用戶ID（可選）"
}
```

**回傳**:
```json
{
  "answer": "AI 回答（含記憶與反思）",
  "memory_used": ["記憶1", "記憶2"],
  "reflection_used": ["反思1"],
  "timestamp": "2025-11-12T18:39:25"
}
```

#### 2. `/api/memory/read` (GET)
**功能**: 讀取指定會話的記憶
- Query 參數: `conversation_id`

#### 3. `/api/memory/search` (POST)
**功能**: 語意搜尋記憶庫
```json
{
  "query": "搜尋關鍵字",
  "limit": 5
}
```

#### 4. `/api/reflection/write` (POST)
**功能**: 儲存新的反思
```json
{
  "conversation_id": "會話ID",
  "reflection_text": "反思內容",
  "quality_score": 0.85,
  "metadata": {}
}
```

#### 5. `/api/reflection/search` (POST)
**功能**: 搜尋相關反思
```json
{
  "query": "搜尋關鍵字",
  "limit": 3
}
```

---

## 🔌 資料庫整合

### 共享資源
Copilot Memory Brain 與小宸光主系統共用：

1. **Redis (Upstash)**
   - 短期記憶快取
   - 24-48 小時 TTL
   - Key 格式: `conversations:{conversation_id}`

2. **Supabase (PostgreSQL)**
   - 表: `xiaochenguang_memories`
   - 透過 `platform` 欄位區分來源（"copilot" vs "web"）
   - 支援向量搜尋（pgvector）

3. **OpenAI API**
   - 模型: `gpt-4o-mini`
   - Embedding: `text-embedding-3-small`

### 資料隔離策略
- **platform 欄位**: 標記資料來源（web/copilot）
- **source 欄位**: 區分不同子系統
- **無衝突設計**: 兩個後端可安全並行運行

---

## 🎨 前端整合

### CopilotWindow.vue
**位置**: `frontend/src/components/CopilotWindow.vue`

**功能**:
- 浮動視窗 UI（可關閉）
- 輸入框 + 送出按鈕
- 狀態提示（處理中/錯誤/成功）
- 顯示記憶與反思來源

**樣式**:
- 深色主題（#1a1a2e 背景）
- 紫色漸變按鈕（#667eea → #764ba2）
- 響應式設計

### ChatInterface.vue 修改
**新增**:
- "Ask Copilot" 按鈕（紫色漸變）
- `copilotWindowVisible` 狀態管理
- `openCopilotWindow()` / `closeCopilotWindow()` 方法

---

## 📦 模組複用策略

### 直接 Import 主系統模組
```python
from backend.modules.memory.redis_interface import RedisInterface
from backend.supabase_handler import get_supabase
from backend.openai_handler import get_openai_client
```

**優勢**:
- ✅ 零代碼重複
- ✅ 自動同步更新
- ✅ 共享配置與連線

**注意**:
- ⚠️ 依賴 sys.path 操作（待優化為 proper package）
- ⚠️ 需確保兩個專案目錄結構穩定

---

## 🚀 部署配置

### Replit 開發環境
```bash
# Workflow 1: 小宸光 AI
Command: python main.py
Port: 5000

# Workflow 2: Copilot Memory Brain
Command: cd copilot-memory-brain/backend && python main.py
Port: 8080
```

### Railway 生產環境
```bash
# Service 1: XiaoChenGuang AI
Start Command: python main.py
Environment: See main backend .env

# Service 2: Copilot Memory Brain
Start Command: cd copilot-memory-brain/backend && python main.py
Environment Variables:
  - REDIS_URL
  - SUPABASE_URL
  - SUPABASE_ANON_KEY
  - OPENAI_API_KEY
  - OPENAI_ORG_ID
  - OPENAI_PROJECT_ID
```

### Cloudflare Pages（前端）
```bash
# Environment Variables
VITE_API_URL=https://ai2.dreamground.net
VITE_COPILOT_API_URL=https://ai2.dreamground.net:8080
```

---

## ⚠️ Architect 審查要點

### ✅ 通過項目
1. 功能性目標達成 - 所有 API 端點正常運作
2. 端口配置正確 - Port 8080 獨立運行
3. 資料庫整合穩定 - Redis/Supabase 共享無衝突
4. 前端整合完整 - CopilotWindow 組件運作良好

### ⚠️ 待優化項目

#### 1. Import 路徑改進
**現狀**: 使用 ad-hoc `sys.path` 操作  
**建議**: 轉為 proper Python package with relative imports

**未來改進方案**:
```python
# 從
sys.path.insert(0, os.path.join(...))
from config import config

# 改為
from copilot_memory_brain.backend.config import config
```

#### 2. 前端 API URL 配置
**已修復**: ✅ 使用 `COPILOT_API_BASE` 環境變數  
**原問題**: 硬編碼 `:8080` 導致部署不靈活

#### 3. 錯誤處理強化
**建議**: 區分不同錯誤類型
- Validation failures
- Upstream service outages (Supabase/OpenAI)
- Unexpected exceptions

**示例改進**:
```python
try:
    # API call
except ValueError as e:
    return JSONResponse(status_code=400, content={"error": "Invalid input", "detail": str(e)})
except ConnectionError as e:
    return JSONResponse(status_code=503, content={"error": "Service unavailable", "detail": str(e)})
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    return JSONResponse(status_code=500, content={"error": "Internal error"})
```

---

## 📂 專案結構

```
copilot-memory-brain/
├── __init__.py                  # Package marker
├── README.md                    # 專案說明
├── PROJECT_SUMMARY.md          # 本文檔
├── requirements.txt            # Python 依賴
│
├── backend/
│   ├── __init__.py
│   ├── main.py                 # FastAPI 主程式
│   ├── config.py               # 配置管理
│   │
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── copilot_router.py  # 主要查詢端點
│   │   ├── memory_router.py   # 記憶讀寫
│   │   └── reflection_router.py # 反思管理
│   │
│   └── modules/
│       ├── __init__.py
│       └── copilot_memory.py   # 記憶整合邏輯
│
└── docs/
    └── DEPLOYMENT.md           # 部署指南
```

---

## 🧪 測試建議

### 手動測試
```bash
# 1. 測試健康檢查
curl http://localhost:8080/health

# 2. 測試 Copilot 查詢
curl -X POST http://localhost:8080/api/ask_copilot \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "我之前跟你聊過什麼？",
    "conversation_id": "test_123",
    "user_id": "test_user"
  }'

# 3. 測試記憶搜尋
curl -X POST http://localhost:8080/api/memory/search \
  -H "Content-Type: application/json" \
  -d '{"query": "測試", "limit": 5}'
```

### 前端測試
1. 開啟小宸光 AI 界面
2. 點擊 "Ask Copilot" 按鈕
3. 輸入問題並送出
4. 驗證回應包含記憶與反思

---

## 🔮 未來擴展

### Phase 2: VS Code Extension
1. 建立 VS Code 外掛專案
2. 使用 TypeScript + VS Code API
3. 整合 Copilot Chat API
4. 連接到 Copilot Memory Brain 後端

### Phase 3: 進階功能
- [ ] 代碼上下文分析（AST parsing）
- [ ] 專案結構理解
- [ ] 自動生成反思（基於代碼變更）
- [ ] 多專案記憶隔離

---

## 📞 支援資訊

**開發者**: AI Agent  
**Architect 審查**: Claude 4.5 Sonnet (Opus 4.1)  
**部署平台**: Railway (後端) + Cloudflare Pages (前端)  
**記憶引擎**: 小宸光 AI 系統

**相關文檔**:
- [部署指南](./docs/DEPLOYMENT.md)
- [主專案 README](../README.md)
- [Replit 開發筆記](../replit.md)

---

**最後更新**: 2025-11-12 18:40 UTC  
**版本**: 1.0.0 - Initial Release  
**狀態**: ✅ Production Ready
