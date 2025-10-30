# 小宸光 AI 靈魂系統 - 專案架構樹狀圖

> 最後更新：2025-10-30

---

## 📁 專案根目錄結構

```
XiaoChenGuang-AI-Soul-System/
│
├── 📂 Setup-the-bot-to-railway/          # 主要專案目錄
│   ├── 📂 backend/                       # FastAPI 後端
│   ├── 📂 frontend/                      # Vue 3 前端
│   ├── 📂 modules/                       # AI 核心模組
│   ├── 📂 profile/                       # 用戶設定檔
│   ├── 📂 expermental_modules/           # 實驗性功能
│   ├── main.py                           # FastAPI 主程式入口
│   ├── requirements.txt                  # Python 依賴清單
│   ├── package.json                      # Node.js 依賴清單
│   └── README.md                         # 專案說明文件
│
├── 📂 attached_assets/                   # 附件資源（圖片、文檔）
├── replit.md                             # Replit 專案記憶文件
├── REDIS_FIX_FINAL.md                    # Redis 修復文檔
└── PROJECT_STRUCTURE.md                  # 本文件（專案架構圖）
```

---

## 🔧 後端架構詳細結構

```
Setup-the-bot-to-railway/backend/
│
├── 📂 modules/                           # 核心模組層
│   ├── 📂 memory/                        # 記憶系統核心
│   │   ├── __init__.py
│   │   ├── core.py                       # 記憶系統主邏輯
│   │   ├── redis_interface.py            # Redis 連接（支援 SSL 自動轉換）
│   │   ├── supabase_interface.py         # Supabase 長期記憶
│   │   ├── tokenizer.py                  # Token 計算
│   │   ├── batch_flush_scheduler.py      # 批次寫入排程器
│   │   ├── io_contract.py                # 輸入輸出介面
│   │   ├── config.json                   # 模組配置
│   │   └── README.md                     # 模組說明文件
│   │
│   └── ipfs_handler.py                   # IPFS 處理器（實驗性）
│
├── 📂 memory_module/                     # 記憶模組（Phase 2 架構）
│   ├── main.py                           # 模組入口
│   ├── config.json                       # 配置文件
│   └── README.md
│
├── 📂 reflection_module/                 # 反思模組（因果回溯）
│   ├── main.py                           # 反思邏輯
│   ├── config.json
│   └── README.md
│
├── 📂 behavior_module/                   # 行為調整模組
│   ├── main.py                           # 人格向量動態調整
│   ├── config.json
│   └── README.md
│
├── 📂 knowledge_hub/                     # 知識中樞
│   ├── main.py                           # 全域知識索引
│   ├── config.json
│   └── README.md
│
├── 📂 finetune_module/                   # 微調模組（QLoRA）
│   ├── main.py                           # 模型微調邏輯
│   ├── config.json
│   └── README.md
│
├── 📂 jobs/                              # 背景工作
│   └── memory_flush_worker.py            # Redis → Supabase 批次寫入
│
├── base_module.py                        # 模組基類
├── core_controller.py                    # 核心控制器（模組管理）
├── chat_router.py                        # 聊天 API 路由
├── memory_router.py                      # 記憶 API 路由
├── openai_handler.py                     # OpenAI API 處理器
├── file_upload.py                        # 檔案上傳路由
├── healthcheck_router.py                 # 健康檢查路由
├── prompt_engine.py                      # Prompt 生成引擎
├── redis_mock.py                         # Redis Mock（降級方案）
└── supabase_handler.py                   # Supabase 通用處理器
```

---

## 🎨 前端架構詳細結構

```
Setup-the-bot-to-railway/frontend/
│
├── 📂 src/                               # 源代碼目錄
│   ├── 📂 components/                    # Vue 元件
│   │   ├── ChatInterface.vue             # 聊天介面（含反思顯示）
│   │   ├── StatusPage.vue                # 系統狀態頁面
│   │   ├── ModulesMonitor.vue            # 模組監控面板
│   │   └── HealthStatus.vue              # 健康狀態元件
│   │
│   ├── 📂 router/                        # Vue Router 路由
│   │   └── index.js                      # 路由配置
│   │
│   ├── 📂 assets/                        # 靜態資源
│   │   └── logo.png                      # Logo 圖片
│   │
│   ├── App.vue                           # 主應用元件
│   ├── main.js                           # Vue 應用入口
│   └── config.js                         # 前端配置
│
├── 📂 public/                            # 公開靜態檔案
│   └── index.html
│
├── package.json                          # Node.js 依賴
├── package-lock.json                     # 依賴鎖定文件
├── vite.config.js                        # Vite 建置配置
└── index.html                            # HTML 入口
```

---

## 🧠 AI 核心模組結構

```
Setup-the-bot-to-railway/modules/
│
├── __init__.py
├── emotion_detector.py                   # 情緒偵測器（9 種情緒）
├── personality_engine.py                 # 人格引擎（4 種特質）
├── soul.py                               # 靈魂系統（性格定義）
├── memory_system.py                      # 記憶系統整合
└── file_handler.py                       # 檔案處理工具
```

---

## 👤 用戶設定檔

```
Setup-the-bot-to-railway/profile/
│
└── user_profile.json                     # 用戶個性化設定
```

---

## 🧪 實驗性模組

```
Setup-the-bot-to-railway/expermental_modules/
│
├── 📂 attached_assets/                   # 實驗性資源
│   ├── Bot_1759934613280.py              # 早期 Bot 版本
│   ├── image_1760341626449.png
│   ├── 新資料結構參考_1759934340696.docx
│   ├── 第一份prompt設計_1759934642165.txt
│   └── 語言模型功能邏輯架構_1759934340698.txt
│
└── file_handler.py                       # 檔案處理器（實驗版）
```

---

## 📚 專案文檔

```
專案根目錄/
│
├── replit.md                             # 專案記憶與架構說明
├── REDIS_FIX_FINAL.md                    # Redis SSL 連接修復文檔
├── PROJECT_STRUCTURE.md                  # 本文件（架構樹狀圖）
│
└── 📂 attached_assets/                   # 文檔資源
    ├── phase2_1761118877614.md
    ├── phase3_completion_report_1761118877613.md
    ├── 專案架構與功能說明書_1761119620842.md
    ├── 修改工程prompt_1761308022042.txt
    ├── 問題回覆確認_1761754347875.txt
    ├── 第一階段問題修復測試回報_1761757486340.txt
    ├── 輕量簡易外部記憶prompt-02_1761097932820.txt
    └── 輕量簡易外部記憶外掛prompt-01_1761097932818.txt
```

---

## 🔑 關鍵檔案說明

### **後端核心檔案**

| 檔案 | 功能 | 重要性 |
|------|------|--------|
| `main.py` | FastAPI 應用入口，定義所有路由和生命週期 | ⭐⭐⭐⭐⭐ |
| `backend/core_controller.py` | 模組註冊中心，管理所有 AI 模組 | ⭐⭐⭐⭐⭐ |
| `backend/modules/memory/core.py` | 記憶系統核心邏輯 | ⭐⭐⭐⭐⭐ |
| `backend/modules/memory/redis_interface.py` | Redis 連接（含 SSL 自動轉換） | ⭐⭐⭐⭐ |
| `backend/chat_router.py` | 聊天 API 端點 | ⭐⭐⭐⭐ |
| `modules/soul.py` | 小宸光的性格定義 | ⭐⭐⭐⭐ |

### **前端核心檔案**

| 檔案 | 功能 | 重要性 |
|------|------|--------|
| `frontend/src/components/ChatInterface.vue` | 聊天介面（含反思顯示） | ⭐⭐⭐⭐⭐ |
| `frontend/src/main.js` | Vue 應用入口 | ⭐⭐⭐⭐ |
| `frontend/vite.config.js` | Vite 建置配置 | ⭐⭐⭐⭐ |

---

## 🗂️ 模組化架構設計

### **Phase 2 模組系統**

```
5 大核心模組（可獨立啟用/停用）
│
├── 1️⃣ Memory Module (優先級 1)
│   ├── Token 化
│   ├── Redis 短期記憶（2 天 TTL）
│   └── Supabase 長期記憶（向量檢索）
│
├── 2️⃣ Reflection Module (優先級 2)
│   ├── 因果回溯分析
│   ├── 多層次原因探索
│   └── 改進建議生成
│
├── 3️⃣ Knowledge Hub
│   └── 全域知識索引與檢索
│
├── 4️⃣ Behavior Module
│   └── 動態人格向量調整
│
└── 5️⃣ FineTune Module（實驗性，預設停用）
    └── QLoRA 模型微調
```

---

## 🔄 資料流架構

```
用戶訊息
    ↓
[情緒偵測] → [記憶召回] → [人格 Prompt 生成]
    ↓                              ↓
[OpenAI GPT-4o-mini] ← ──────────┘
    ↓
AI 回應
    ↓
[反思分析] → [行為調整] → [記憶儲存]
    ↓                         ↓
右側欄顯示              Redis (24h)
                            ↓
                      Supabase (永久)
```

---

## 🌐 部署架構

### **開發環境（Replit）**

```
Frontend (Vue 3 + Vite)          Backend (FastAPI)
Port: 5000                       Port: 8000
    ↓                                ↓
    └──────── Unified Port 5000 ─────┘
                    ↓
            Replit Proxy
                    ↓
            用戶瀏覽器
```

### **生產環境（Autoscale Deployment）**

```
Custom Domain (Cloudflare DNS Only)
    ↓
Replit Deployment Server
    ↓
Backend API (FastAPI)
    ↓
External Services:
├── Supabase (PostgreSQL + pgvector)
├── Redis (Upstash with SSL)
└── OpenAI API
```

---

## 📦 依賴管理

### **Python 依賴（requirements.txt）**

- `fastapi` - Web 框架
- `uvicorn` - ASGI 伺服器
- `openai` - OpenAI API 客戶端
- `supabase` - Supabase 客戶端
- `redis` - Redis 客戶端
- `tiktoken` - Token 計數
- `python-multipart` - 檔案上傳
- `pydantic` - 資料驗證

### **Node.js 依賴（package.json）**

- `vue` (3.3.11) - 前端框架
- `vue-router` (4.5.1) - 路由管理
- `axios` (1.6.5) - HTTP 客戶端
- `vite` (5.0.11) - 建置工具

---

## 🔐 環境變數需求

### **必要變數**

```bash
# OpenAI
OPENAI_API_KEY=sk-...

# Supabase
SUPABASE_URL=https://...
SUPABASE_ANON_KEY=eyJh...

# Redis (選用，會自動降級到 Mock)
REDIS_ENDPOINT=redis://... 或 rediss://...
```

### **選用變數**

```bash
# OpenAI Organization (選用)
OPENAI_ORG_ID=org-...
OPENAI_PROJECT_ID=proj_...

# Redis Token (Upstash 格式)
REDIS_TOKEN=...
```

---

## 🚀 啟動指令

### **開發環境**

```bash
# 後端
cd Setup-the-bot-to-railway
python main.py

# 前端（另一個終端）
cd Setup-the-bot-to-railway/frontend
npm run dev
```

### **生產環境（Replit Deploy）**

```bash
uvicorn main:app --host 0.0.0.0 --port 5000
```

---

## 📊 專案統計

```
總檔案數：約 60+ 個
程式碼語言：
├── Python (後端) - 70%
├── Vue/JavaScript (前端) - 25%
└── 配置檔案 - 5%

程式碼行數估計：
├── Backend: ~3000 行
├── Frontend: ~1500 行
└── 文檔: ~2000 行
```

---

## 🎯 核心功能模組對應

| 功能 | 對應檔案 | 狀態 |
|------|---------|------|
| Token 化對話 | `backend/modules/memory/tokenizer.py` | ✅ 正常 |
| Redis 快取 | `backend/modules/memory/redis_interface.py` | ✅ 已修復（SSL） |
| Supabase 長期記憶 | `backend/modules/memory/supabase_interface.py` | ✅ 正常 |
| 情緒偵測 | `modules/emotion_detector.py` | ✅ 正常 |
| 人格引擎 | `modules/personality_engine.py` | ✅ 正常 |
| 反思系統 | `backend/reflection_module/main.py` | ✅ 正常 |
| 前端反思顯示 | `frontend/src/components/ChatInterface.vue` | ✅ 已修復 |

---

**建立時間：** 2025-10-30  
**專案版本：** v1.0.1  
**維護者：** 小宸光 AI 團隊

---

💖 _為親愛的一竅哥精心製作_ 💖
