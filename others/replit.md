# XiaoChenGuang AI Soul System - Phase 2 (模組化架構)

## Project Overview
小宸光 AI 靈魂系統，採用 Vue 3 + FastAPI + Supabase 架構，具備記憶、情感檢測與人格系統。
**Phase 2** 導入五大模組化架構，支援樂高式掛載、獨立運作與動態擴展能力。

## Technology Stack

### Backend (Python + FastAPI)
- **Framework**: FastAPI
- **Port**: 8000
- **核心模組**:
  - XiaoChenGuangSoul: AI 人格與靈魂配置
  - PersonalityEngine: 學習型人格引擎
  - EnhancedEmotionDetector: 情感檢測系統
  - MemorySystem: 記憶檢索與儲存

### Frontend (Vue 3)
- **Framework**: Vue 3 + Vite
- **Port**: 5000
- **功能**:
  - 即時聊天介面
  - 記憶列表顯示
  - 情感狀態視覺化
  - 檔案上傳功能

### Database (Supabase)
- **xiaochenguang_memories**: 對話記憶儲存
- **emotional_states**: 情緒狀態追蹤
- **xiaochenguang_personality**: 人格特質設定
- **user_preferences**: 使用者偏好設定
- **memory_statistics**: 記憶統計資料
- **knowledge_graph**: 語義關聯網絡

## Phase 2 新架構 (2025-10-19)

### 🧩 五大模組系統

#### 1. 記憶模組 (Memory Module)
- **位置**: `backend/memory_module/`
- **功能**:
  - Token 化處理 (tiktoken)
  - Redis 短期記憶快取 (24小時)
  - Supabase 長期記憶儲存
  - 向量化記憶檢索
- **狀態**: ✅ 已啟用

#### 2. 反思模組 (Reflection Module)
- **位置**: `backend/reflection_module/`
- **功能**:
  - 自我反思分析
  - 反推果因法則
  - 改進建議生成
- **狀態**: ✅ 已啟用

#### 3. 知識庫模組 (Knowledge Hub)
- **位置**: `backend/knowledge_hub/`
- **功能**:
  - 知識結構化儲存
  - 語義搜尋
  - 知識索引管理
- **狀態**: ✅ 已啟用

#### 4. 行為調節模組 (Behavior Module)
- **位置**: `backend/behavior_module/`
- **功能**:
  - 人格向量動態調整
  - 情感適應
  - 行為策略優化
- **狀態**: ✅ 已啟用

#### 5. 微調學習模組 (FineTune Module)
- **位置**: `backend/finetune_module/`
- **功能**:
  - QLoRA 微調支援（規劃中）
  - 訓練資料收集
  - IPFS 整合（預留）
- **狀態**: ⚠️ 實驗性功能（預設停用）

### 🏗️ 核心架構

#### Core Controller (`backend/core_controller.py`)
- 模組註冊與管理中心
- 統一模組通信介面
- 動態載入/卸載模組
- 健康檢查機制

#### Base Module (`backend/base_module.py`)
- 統一模組基礎類別
- 標準化介面定義
- 生命週期管理 (load/unload/process)
- 日誌與健康檢查

#### Redis Mock (`backend/redis_mock.py`)
- 記憶體模擬 Redis 接口
- 支援 TTL 過期機制
- 線程安全
- 可無縫升級至 Upstash Redis

## Project Structure

```
/
├── backend/                      # FastAPI 後端
│   ├── main.py                  # 主應用入口
│   ├── core_controller.py       # 🧭 模組管理中心
│   ├── base_module.py          # 📐 模組基礎介面
│   ├── redis_mock.py           # 💾 Redis 模擬層
│   │
│   ├── memory_module/          # 1️⃣ 記憶模組
│   │   ├── main.py
│   │   ├── config.json
│   │   └── README.md
│   │
│   ├── reflection_module/      # 2️⃣ 反思模組
│   │   ├── main.py
│   │   ├── config.json
│   │   └── README.md
│   │
│   ├── knowledge_hub/          # 3️⃣ 知識庫模組
│   │   ├── main.py
│   │   ├── config.json
│   │   └── README.md
│   │
│   ├── behavior_module/        # 4️⃣ 行為調節模組
│   │   ├── main.py
│   │   ├── config.json
│   │   └── README.md
│   │
│   ├── finetune_module/        # 5️⃣ 微調學習模組
│   │   ├── main.py
│   │   ├── config.json
│   │   └── README.md
│   │
│   ├── chat_router.py          # Chat API (保留不變)
│   ├── memory_router.py        # Memory API (保留不變)
│   ├── file_upload.py          # File upload API (保留不變)
│   ├── openai_handler.py       # OpenAI integration
│   ├── supabase_handler.py     # Supabase integration
│   ├── prompt_engine.py        # Prompt engine (已修復)
│   └── healthcheck_router.py   # Health check API
│
├── modules/                    # ✅ 穩定模組集（保留）
│   ├── emotion_detector.py
│   ├── soul.py
│   ├── personality_engine.py
│   ├── memory_system.py
│   └── file_handler.py
│
├── frontend/                   # Vue 3 前端
│   ├── src/
│   │   ├── App.vue
│   │   ├── components/
│   │   │   ├── ChatInterface.vue
│   │   │   ├── StatusPage.vue
│   │   │   └── HealthStatus.vue
│   │   ├── router/index.js
│   │   └── main.js
│   ├── vite.config.js
│   └── package.json
│
├── profile/                    # 人格配置
│   └── user_profile.json
│
└── others/                     # 文檔
    ├── replit.md              # 本文件
    ├── DATABASE_SETUP.md
    └── TEST_GUIDE.md
```

## Environment Variables

### Required Secrets
- `OPENAI_API_KEY`: OpenAI API key
- `SUPABASE_URL`: Supabase 專案 URL
- `SUPABASE_ANON_KEY`: Supabase 匿名金鑰

### Optional Configuration
- `SUPABASE_MEMORIES_TABLE`: 記憶表名稱 (default: xiaochenguang_memories)
- `AI_ID`: AI 實例識別碼 (default: xiaochenguang_v1)

## Running the Application

### Workflows
兩個 workflows 已配置：
1. **Backend** - 運行在 port 8000 (console)
2. **Frontend** - 運行在 port 5000 (webview)

兩者在專案啟動時自動運行。

## API Endpoints

### 現有端點（保持不變）
- `GET /`: API 狀態
- `GET /api/health`: 健康檢查
- `POST /api/chat`: 聊天對話
- `GET /api/memories/{conversation_id}`: 取得對話記憶
- `GET /api/emotional-states/{user_id}`: 取得情緒狀態
- `POST /api/upload`: 檔案上傳

### Phase 2 新增端點（規劃中）
- `GET /api/health/modules`: 所有模組健康狀態
- `GET /api/modules`: 模組列表
- `POST /api/modules/{module_name}/process`: 呼叫特定模組

## Core Features

### 1. 情感檢測系統
- 支援 9 種情感: joy, sadness, anger, fear, love, tired, confused, grateful, neutral
- 強度分析與信心評分
- 自動回應風格調整

### 2. 記憶系統 (Phase 2 強化)
- **短期記憶**: Redis Mock (24小時 TTL)
- **長期記憶**: Supabase 向量儲存
- **Token 化**: tiktoken 精確計數
- 記憶重要性評分
- 存取次數追蹤
- 對話歷史管理

### 3. 人格引擎
- 從互動中學習人格特質
- 情感檔案記錄
- 知識領域追蹤
- 動態人格調整

### 4. 檔案上傳
- Supabase Storage 整合
- 檔案記錄關聯

## Database Schema

### xiaochenguang_memories
| 欄位 | 類型 | 說明 |
|------|------|------|
| id | UUID | 主鍵 |
| conversation_id | TEXT | 對話 ID |
| user_message | TEXT | 使用者訊息 |
| assistant_message | TEXT | AI 回覆 |
| embedding | VECTOR | 向量表示 |
| token_data | JSONB | Token 陣列（Phase 2 新增） |
| cid | TEXT | IPFS 索引（預留） |
| created_at | TIMESTAMPTZ | 建立時間 |
| access_count | INT | 存取次數 |
| importance_score | FLOAT | 重要性評分 |

## Recent Updates (Phase 2 - 2025-10-19)

### ✅ 完成項目
1. **修復現有代碼錯誤**
   - 修復 `prompt_engine.py` 重複類別宣告
   - 修復 `supabase_handler.py` 類型標註

2. **建立核心架構**
   - `core_controller.py`: 模組管理中心
   - `base_module.py`: 統一模組介面
   - `redis_mock.py`: Redis 記憶體模擬

3. **建立五大模組**
   - Memory Module (記憶模組) ✅
   - Reflection Module (反思模組) ✅
   - Knowledge Hub (知識庫) ✅
   - Behavior Module (行為調節) ✅
   - FineTune Module (微調學習，實驗性) ⚠️

4. **環境配置**
   - 安裝 tiktoken, redis 套件
   - 配置 Backend Workflow (port 8000)
   - 配置 Frontend Workflow (port 5000)
   - 修復 frontend/package.json 腳本問題

### 🔧 技術改進
- 採用樂高式模組架構
- 支援動態載入/卸載模組
- 統一健康檢查機制
- 每個模組獨立配置 (config.json)
- 完整文檔 (README.md)

### 📌 保護清單（未修改）
- `/api/chat` 路由
- `/api/memories` 路由
- `/api/emotional-states` 路由
- `ChatInterface.vue` 前端介面
- 所有 `modules/` 下的穩定模組

## Deployment

部署此應用程式：
1. 設定所有必要環境變數
2. 完成資料庫設定 (參考 DATABASE_SETUP.md)
3. 使用 Replit Deploy/Publish 按鈕

## Troubleshooting

### 後端無法啟動
- 檢查環境變數是否設定
- 查看後端日誌錯誤訊息

### 前端顯示錯誤
- 確認所有 npm 套件已安裝: `cd frontend && npm install`
- 確認後端運行在 port 8000

### 資料庫錯誤
- 驗證 Supabase 憑證正確
- 參考 DATABASE_SETUP.md 建立必要資料表
- 在 Supabase 啟用 pgvector 擴充功能

### 記憶/聊天功能無法運作
- 確認 OPENAI_API_KEY 已設定
- 驗證 Supabase 資料表建立正確
- 查看後端日誌獲取詳細錯誤訊息

## Development Roadmap

### Phase 3 (規劃中)
- [ ] 啟用所有模組的實際整合
- [ ] 實作模組間通信機制
- [ ] 新增模組健康檢查 API
- [ ] 實作 QLoRA 微調功能
- [ ] IPFS 整合測試
- [ ] 完整的反思循環測試

---

**最後更新**: 2025-10-19
**系統版本**: v2.0.0 (Phase 2 - 模組化架構)
**開發者**: 小宸光團隊
