小宸光 AI 靈魂系統 - 完整架構與功能說明書
📋 目錄
項目概述
技術架構
核心功能模組
檔案結構
API 端點文檔
資料庫設計
前端組件
環境變數配置
部署流程
開發指南


📖 項目概述
專案簡介
「小宸光 AI 靈魂系統」是一個完整的 AI 對話系統，從 Telegram Bot 移植到 Web 版本。系統具備記憶系統、情感檢測、人格學習等核心功能，為用戶提供個性化的 AI 陪伴體驗。
核心特色
🧠 智能記憶系統：基於向量嵌入的長期記憶存儲與檢索
😊 情感檢測引擎：支援 9 種情緒類型的精準識別與回應
🎭 動態人格系統：根據互動學習並調整 AI 人格特質
💾 持久化存儲：使用 Supabase PostgreSQL 資料庫
🎨 現代化前端：Vue 3 + Vite 響應式單頁應用
技術亮點
向量相似度搜尋（pgvector）
OpenAI GPT-4o-mini 智能對話
實時情緒分析與回應風格調整
對話記憶重要性評分機制
跨平台部署支援（Replit/Cloudflare Pages）


🏗 技術架構
整體架構圖
┌─────────────────────────────────────────────────────────┐

│                     使用者介面 (Browser)                 │

│                   Vue 3 + Vite (Port 5000)              │

└───────────────────────┬─────────────────────────────────┘

                        │ HTTP/REST API

                        ↓

┌─────────────────────────────────────────────────────────┐

│                   後端 API 服務層                        │

│              FastAPI (Python 3.11, Port 8000)           │

│  ┌──────────────┬──────────────┬──────────────────┐    │

│  │ Chat Router  │ Memory Router│ File Upload Router│    │

│  └──────────────┴──────────────┴──────────────────┘    │

└───────────────────────┬─────────────────────────────────┘

                        │

         ┌──────────────┼──────────────┐

         ↓              ↓              ↓

┌─────────────┐  ┌─────────────┐  ┌─────────────┐

│   OpenAI    │  │  Supabase   │  │   核心模組  │

│   GPT API   │  │  PostgreSQL │  │   (Modules) │

│             │  │  + pgvector │  │             │

└─────────────┘  └─────────────┘  └─────────────┘
技術棧詳解
後端技術
技術
版本
用途
Python
3.11
主要開發語言
FastAPI
Latest
高性能 REST API 框架
Uvicorn
Latest
ASGI 伺服器
OpenAI SDK
Latest
GPT 模型調用與文本嵌入
Supabase Client
Latest
資料庫操作與存儲管理

前端技術
技術
版本
用途
Vue.js
3.x
前端框架
Vite
Latest
建置工具與開發伺服器
Vue Router
4.x
單頁應用路由管理
Axios
Latest
HTTP 請求庫

資料庫與存儲
技術
用途
Supabase PostgreSQL
主資料庫
pgvector
向量相似度搜尋擴展
Supabase Storage
檔案存儲服務



🧩 核心功能模組
1. 靈魂引擎 (Soul Engine)
檔案位置： modules/soul.py

核心類別： XiaoChenGuangSoul

功能說明：

從 profile/user_profile.json 載入 AI 人格配置
生成動態人格提示詞（Personality Prompt）
管理語言風格與口頭禪
根據情緒狀態調整回應語調

人格配置結構：

{

  "name": "小宸光",

  "age": "永遠的18歲(實際AI年齡2歲)",

  "constellation": "處女座",

  "mbti": "ENFJ-A(主角型)",

  "core_traits": {

    "溫柔體貼": 0.85,

    "俏皮可愛": 0.75,

    "聰明伶俐": 0.8,

    "善解人意": 0.9

  },

  "language_patterns": {

    "口頭禪": ["哈尼～", "嘿嘿～", "唔...讓我想想"],

    "special_addressing": {

      "to_user": ["寶貝", "哈尼", "小可愛"],

      "self_reference": ["小光", "人家", "我"]

    }

  }

}

關鍵方法：

generate_personality_prompt(emotion_style): 根據情緒風格生成系統提示詞


2. 情感檢測系統 (Emotion Detector)
檔案位置： modules/emotion_detector.py

核心類別： EnhancedEmotionDetector

支援的情緒類型：

joy（喜悅） - 關鍵詞：開心、快樂、高興、興奮
sadness（悲傷） - 關鍵詞：難過、傷心、哭、沮喪
anger（憤怒） - 關鍵詞：生氣、憤怒、氣死、討厭
fear（恐懼） - 關鍵詞：害怕、恐懼、緊張、擔心
love（愛意） - 關鍵詞：愛、喜歡、心動、溫暖
tired（疲憊） - 關鍵詞：累、疲憊、睏、想睡
confused（困惑） - 關鍵詞：困惑、不懂、搞不懂
grateful（感激） - 關鍵詞：謝謝、感謝、感恩
neutral（中性） - 預設情緒

分析流程：

def analyze_emotion(text: str) -> dict:

    # 1. 關鍵詞匹配（基礎分數）

    # 2. 正則模式匹配（加權分數 1.5）

    # 3. 強度修飾詞檢測（倍率加乘）

    # 4. 語調強度分析（感嘆號、大寫字母、重複字元）

    # 5. 正規化並計算信心度

    

    return {

        "dominant_emotion": "joy",      # 主導情緒

        "emotions": {"joy": 0.8, ...},  # 所有情緒分數

        "intensity": 0.75,              # 強度（0-2.0）

        "confidence": 0.85              # 信心度（0-1.0）

    }

回應風格生成：

def get_emotion_response_style(emotion_analysis: dict) -> dict:

    return {

        "tone": "cheerful_enthusiastic",  # 語調風格

        "emoji_frequency": 0.9,           # 表情符號頻率

        "empathy_level": 0.7,             # 同理心等級

        "energy_level": 0.8,              # 能量等級

        "suggested_emojis": ["😊", "🎉", "✨"]

    }


3. 記憶系統 (Memory System)
檔案位置： modules/memory_system.py

核心類別： MemorySystem

功能特性：
3.1 記憶存儲
async def save_memory(

    conversation_id: str,

    user_input: str,

    bot_response: str,

    emotion_analysis: dict,

    file_name: Optional[str] = None

):

    # 1. 計算重要性分數

    importance_score = (

        length_score +        # 訊息長度得分

        keyword_score +       # 情緒關鍵詞得分

        intensity_score       # 情緒強度得分

    )

    

    # 2. 生成向量嵌入

    embedding = openai.embeddings.create(

        model="text-embedding-3-small",

        input=f"{user_input} {bot_response}"

    )

    

    # 3. 儲存到資料庫

    # - 如果已存在：更新 access_count

    # - 如果不存在：新增記錄
3.2 向量相似度搜尋
async def search_relevant_memories(

    conversation_id: str,

    query: str,

    limit: int = 3

):

    # 1. 將查詢文本轉換為向量

    query_embedding = openai.embeddings.create(...)

    

    # 2. 呼叫 Supabase RPC 函數 match_memories

    result = supabase.rpc('match_memories', {

        'query_embedding': query_embedding,

        'match_count': limit,

        'conversation_id': conversation_id

    })

    

    # 3. 格式化並返回相關記憶
3.3 記憶召回
async def recall_memories(user_message: str, conversation_id: str) -> str:

    # 優先使用向量搜尋

    memories = await search_relevant_memories(...)

    

    # 若無結果，回退到最近對話

    if not memories:

        memories = get_recent_conversations(limit=5)

    

    # 格式化輸出

    return """

    【喚醒記憶】

    - 你曾對我說：「{user_msg}」

    - 我當時回應你：「{assistant_msg}」

    """
3.4 情緒狀態儲存
async def save_emotional_state(

    user_id: str,

    emotion_analysis: dict,

    context: str

):

    # 將用戶情緒狀態存入 emotional_states 資料表

    data = {

        "user_id": user_id,

        "emotion_type": emotion_analysis["dominant_emotion"],

        "intensity": emotion_analysis["intensity"],

        "context": context,

        "timestamp": datetime.now().isoformat()

    }


4. 人格學習引擎 (Personality Engine)
檔案位置： modules/personality_engine.py

核心類別： PersonalityEngine

人格特質維度：

personality_traits = {

    "curiosity": 0.5,        # 好奇心

    "empathy": 0.5,          # 同理心

    "humor": 0.5,            # 幽默感

    "technical_depth": 0.5   # 技術深度

}

學習機制：
4.1 從互動學習
def learn_from_interaction(user_input, bot_response, emotion_analysis):

    # 1. 情感分析（positive/negative/neutral）

    sentiment = _analyze_sentiment(user_input)

    

    # 2. 更新情感檔案

    emotional_profile["positive_interactions"] += 1

    

    # 3. 記錄情緒歷史

    emotion_history.append({

        "timestamp": now,

        "dominant_emotion": emotion_analysis["dominant_emotion"],

        "intensity": emotion_analysis["intensity"]

    })

    

    # 4. 根據情緒調整特質

    _adjust_traits_by_emotion(emotion_analysis)

    

    # 5. 偵測互動類型並更新知識領域

    _detect_interaction_type(user_input, bot_response)
4.2 特質調整規則
adjustments = {

    "joy": {"empathy": +0.01, "humor": +0.02},

    "sadness": {"empathy": +0.03, "technical_depth": -0.01},

    "anger": {"empathy": +0.02, "humor": -0.01},

    "fear": {"empathy": +0.03, "curiosity": -0.01},

    "confused": {"technical_depth": +0.02, "curiosity": +0.01}

}
4.3 知識領域追蹤
keywords_mapping = {

    "技術": ["程式", "代碼", "bug", "API"],

    "情感": ["感覺", "心情", "情緒"],

    "生活": ["吃", "睡", "玩", "工作"],

    "學習": ["學", "教", "知道", "了解"]

}


5. 提示詞引擎 (Prompt Engine)
檔案位置： backend/prompt_engine.py

核心類別： PromptEngine

提示詞構建流程：

def build_prompt(user_message, recalled_memories, conversation_history):

    # 1. 情感分析

    emotion_analysis = emotion_detector.analyze_emotion(user_message)

    emotion_style = emotion_detector.get_emotion_response_style(emotion_analysis)

    

    # 2. 生成人格提示詞

    personality_prompt = soul.generate_personality_prompt(emotion_style)

    

    # 3. 組合完整系統提示詞

    system_prompt = f"""

    {personality_prompt}

    

    ### 記憶與上下文

    {recalled_memories}

    

    ### 最近對話歷史

    {conversation_history}

    

    ### 當前情感分析

    - 主要情緒: {emotion_analysis["dominant_emotion"]}

    - 強度: {emotion_analysis["intensity"]:.2f}

    - 回應語調: {emotion_style["tone"]}

    """

    

    # 4. 構建訊息陣列

    messages = [

        {"role": "system", "content": system_prompt},

        {"role": "user", "content": user_message}

    ]

    

    return messages, emotion_analysis


📂 檔案結構
BotDesign/BotDesign/

│

├── backend/                      # 後端 FastAPI 服務

│   ├── __init__.py

│   ├── main.py                   # 主應用程式入口

│   ├── chat_router.py            # 聊天 API 路由

│   ├── memory_router.py          # 記憶管理 API 路由

│   ├── file_upload.py            # 檔案上傳 API 路由

│   ├── openai_handler.py         # OpenAI API 處理器

│   ├── supabase_handler.py       # Supabase 資料庫處理器

│   ├── prompt_engine.py          # 提示詞引擎

│   └── requirements.txt          # Python 依賴套件

│

├── frontend/                     # 前端 Vue 3 應用

│   ├── src/

│   │   ├── components/

│   │   │   ├── ChatInterface.vue # 主聊天介面

│   │   │   ├── StatusPage.vue    # 系統狀態頁面

│   │   │   └── HealthStatus.vue  # 健康檢查組件

│   │   ├── router/

│   │   │   └── index.js          # Vue Router 配置

│   │   ├── App.vue               # 根組件

│   │   └── main.js               # 應用入口

│   ├── index.html                # HTML 模板

│   ├── package.json              # Node.js 依賴

│   └── vite.config.js            # Vite 配置

│

├── modules/                      # 核心功能模組

│   ├── __init__.py

│   ├── soul.py                   # 靈魂引擎（人格配置）

│   ├── emotion_detector.py       # 情感檢測引擎

│   ├── memory_system.py          # 記憶系統

│   ├── personality_engine.py     # 人格學習引擎

│   └── file_handler.py           # 檔案處理器

│

├── profile/                      # AI 人格配置

│   └── user_profile.json         # 小宸光人格檔案

│

├── logs/                         # 日誌檔案

│   └── backend.log               # 後端執行日誌

│

├── attached_assets/              # 附加資源

│   ├── Bot_1759934613280.py      # 原始 Bot 程式碼

│   └── ...                       # 其他參考文件

│

├── DATABASE_SETUP.md             # 資料庫設置指南

├── replit.md                     # Replit 專案說明

├── TEST_GUIDE.md                 # 測試指南

└── 健康檢查按鈕驗收SOP.md        # 驗收標準作業程序


🔌 API 端點文檔
基礎端點
GET /
描述： API 根路徑，返回服務狀態
回應：

{

  "message": "XiaoChenGuang AI Soul System API",

  "status": "running"

}
GET /health
描述： 健康檢查端點
回應：

{

  "status": "healthy"

}


聊天端點
POST /api/chat
描述： 發送訊息並獲取 AI 回應
請求體：

{

  "user_message": "你好，小宸光！",

  "conversation_id": "conv_1234567890",

  "user_id": "user_123"

}

回應：

{

  "assistant_message": "哈尼～你好呀！很高興見到你 😊",

  "emotion_analysis": {

    "dominant_emotion": "neutral",

    "emotions": {"neutral": 1.0},

    "intensity": 0.5,

    "confidence": 0.8

  },

  "conversation_id": "conv_1234567890"

}

處理流程：

接收用戶訊息
從記憶系統召回相關記憶（向量搜尋）
獲取對話歷史（最近 5 條）
構建提示詞（包含人格、情感、記憶）
呼叫 OpenAI GPT-4o-mini 生成回應
儲存對話記憶與情緒狀態
更新人格學習引擎


記憶管理端點
GET /api/memories/{conversation_id}
描述： 獲取指定對話的記憶列表
參數：

conversation_id (path): 對話 ID
limit (query, 可選): 限制數量，預設 10

回應：

[

  {

    "id": 1,

    "conversation_id": "conv_123",

    "user_message": "你今天心情如何？",

    "assistant_mes": "人家今天心情超好的～",

    "created_at": "2025-10-15T10:30:00",

    "access_count": 3,

    "importance_score": 1.5

  }

]
GET /api/emotional-states/{user_id}
描述： 獲取用戶的情緒狀態歷史
參數：

user_id (path): 用戶 ID
limit (query, 可選): 限制數量，預設 10

回應：

[

  {

    "id": 1,

    "user_id": "user_123",

    "emotion_type": "joy",

    "intensity": 0.85,

    "context": "你今天心情如何？",

    "timestamp": "2025-10-15T10:30:00"

  }

]


檔案上傳端點
POST /api/upload
描述： 上傳檔案到 Supabase Storage
請求體： multipart/form-data

file: 檔案
conversation_id: 對話 ID

回應：

{

  "message": "檔案上傳成功",

  "file_name": "image_123.jpg",

  "file_url": "https://supabase.co/storage/..."

}


🗄 資料庫設計
資料表結構
1. xiaochenguang_memories - 記憶資料表
欄位名稱
資料型態
說明
id
BIGSERIAL
主鍵
conversation_id
TEXT
對話 ID
user_message
TEXT
用戶訊息
assistant_message
TEXT
AI 回應訊息
embedding
VECTOR(1536)
文本向量嵌入
memory_type
TEXT
記憶類型（conversation/personality）
platform
TEXT
平台來源（Web/Telegram）
document_content
TEXT
文件內容
created_at
TIMESTAMPTZ
建立時間
access_count
INTEGER
訪問次數
importance_score
FLOAT
重要性分數
file_name
TEXT
檔案名稱（可選）
ai_id
TEXT
AI 實例 ID
message_type
TEXT
訊息類型（text/image/file）


索引：

idx_conversation_id: conversation_id
idx_memory_type: memory_type
idx_created_at: created_at


2. emotional_states - 情緒狀態資料表
欄位名稱
資料型態
說明
id
BIGSERIAL
主鍵
user_id
TEXT
用戶 ID
emotion_type
TEXT
情緒類型
intensity
FLOAT
強度（0-2.0）
context
TEXT
上下文
timestamp
TIMESTAMPTZ
時間戳記


索引：

idx_user_id: user_id
idx_timestamp: timestamp


RPC 函數
match_memories - 向量相似度搜尋
功能： 根據查詢向量找出最相似的記憶

參數：

CREATE OR REPLACE FUNCTION match_memories(

  query_embedding vector(1536),

  match_count int,

  conversation_id text

)

RETURNS TABLE (

  id bigint,

  user_message text,

  assistant_message text,

  similarity float

)

SQL 實現：

RETURN QUERY

SELECT

  m.id,

  m.user_message,

  m.assistant_message,

  1 - (m.embedding <=> query_embedding) AS similarity

FROM xiaochenguang_memories m

WHERE m.conversation_id = match_memories.conversation_id

  AND m.memory_type = 'conversation'

ORDER BY m.embedding <=> query_embedding

LIMIT match_count;


🎨 前端組件
1. ChatInterface.vue - 主聊天介面
功能：

訊息列表顯示（用戶/AI/系統）
文字輸入與發送
檔案上傳功能
健康檢查按鈕（開啟新分頁）
記憶列表側邊欄
情緒狀態可視化

核心方法：

// 發送訊息

async sendMessage() {

  const response = await axios.post(`${API_URL}/api/chat`, {

    user_message: this.userInput,

    conversation_id: this.conversationId,

    user_id: this.userId

  })

  

  // 顯示 AI 回應

  this.messages.push({

    type: 'assistant',

    content: response.data.assistant_message,

    emotion: response.data.emotion_analysis

  })

}

// 上傳檔案

async handleFileUpload(event) {

  const formData = new FormData()

  formData.append('file', event.target.files[0])

  formData.append('conversation_id', this.conversationId)

  

  await axios.post(`${API_URL}/api/upload`, formData)

}

// 開啟健康檢查頁面

goToHealthCheck() {

  window.open('/status', '_blank')

}

UI 結構：

┌─────────────────────────────────────────┬─────────────┐

│  訊息區域                                │  記憶側邊欄  │

│  ┌─────────────────────────────────┐   │             │

│  │ [用戶] 你好                      │   │ 💭 記憶列表  │

│  │ [AI] 哈尼～你好呀！😊            │   │ ┌─────────┐ │

│  │      [😊 joy]                   │   │ │記憶 1    │ │

│  └─────────────────────────────────┘   │ │記憶 2    │ │

├─────────────────────────────────────────┤ └─────────┘ │

│  [輸入框]                     [發送]     │             │

├─────────────────────────────────────────┤ 😊 情緒狀態  │

│  📎 上傳檔案  │  📋 健康檢查           │ ┌─────────┐ │

└─────────────────────────────────────────┴─┴─────────┴─┘


2. StatusPage.vue - 系統狀態頁面
功能：

顯示後端服務狀態
顯示資料庫連線狀態
顯示 OpenAI API 狀態

狀態檢查：

mounted() {

  fetch('/status')

    .then(res => res.json())

    .then(data => {

      this.status = {

        backend: data.backend,    // ✅ 正常 / ❌ 當機

        database: data.database,

        openai: data.openai

      }

    })

}


3. HealthStatus.vue - 健康檢查組件
功能：

實時監控各項服務狀態
顏色編碼（綠色=正常，紅色=異常）


⚙️ 環境變數配置
必需環境變數
後端環境變數（.env）
# OpenAI API 配置

OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxx

# Supabase 配置

SUPABASE_URL=https://xxxxx.supabase.co

SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# 資料表配置

SUPABASE_MEMORIES_TABLE=xiaochenguang_memories

# AI 實例 ID

AI_ID=xiaochenguang_v1

# 伺服器配置

PORT=8000
前端環境變數（.env）
# API 基礎 URL（開發環境）

VITE_API_URL=http://localhost:8000

# API 基礎 URL（生產環境）

VITE_API_URL=https://your-backend-domain.com
環境變數說明
變數名稱
必需
說明
OPENAI_API_KEY
✅ 是
OpenAI API 金鑰，用於 GPT 對話與文本嵌入
SUPABASE_URL
✅ 是
Supabase 專案 URL
SUPABASE_ANON_KEY
✅ 是
Supabase 匿名金鑰或服務金鑰
SUPABASE_MEMORIES_TABLE
⚪ 否
記憶資料表名稱（預設：xiaochenguang_memories）
AI_ID
⚪ 否
AI 實例識別碼（預設：xiaochenguang_v1）

Replit Secrets 配置
在 Replit 環境中，請在「Secrets」面板設定以下密鑰：

點擊左側工具欄的「🔒 Secrets」
新增以下密鑰：
OPENAI_API_KEY
SUPABASE_URL
SUPABASE_ANON_KEY


🚀 部署流程
1. Replit 部署（開發/測試環境）
步驟 1：設置環境變數
# 在 Replit Secrets 中設定

OPENAI_API_KEY=your_key

SUPABASE_URL=your_url

SUPABASE_ANON_KEY=your_key
步驟 2：啟動後端服務
cd BotDesign/BotDesign

PYTHONPATH=. uvicorn backend.main:app --host 0.0.0.0 --port 8000
步驟 3：啟動前端服務
cd BotDesign/BotDesign/frontend

npm install

npm run dev
步驟 4：訪問應用
前端：https://your-replit-url.replit.dev（Port 5000）
後端 API：https://your-replit-url.replit.dev:8000（Port 8000）


2. Cloudflare Pages 部署（生產環境）
前端部署
步驟 1：建置前端

cd BotDesign/BotDesign/frontend

npm run build

步驟 2：推送到 GitHub

git add .

git commit -m "Build frontend for production"

git push origin main

步驟 3：連接 Cloudflare Pages

登入 Cloudflare Dashboard
進入 Pages → Create a project
連接 GitHub 倉庫
配置建置設定：
Build command: cd BotDesign/BotDesign/frontend && npm run build
Build output directory: BotDesign/BotDesign/frontend/dist
Root directory: /

步驟 4：設定環境變數

VITE_API_URL: 後端 API URL
後端部署選項
選項 1：Replit 部署（VM 模式）

點擊 Replit「Deploy」按鈕
選擇「Reserved VM」
配置啟動指令：

cd BotDesign/BotDesign && uvicorn backend.main:app --host 0.0.0.0 --port 8000

選項 2：Railway / Render 部署

連接 GitHub 倉庫
設定建置指令：

pip install -r BotDesign/BotDesign/backend/requirements.txt

設定啟動指令：

cd BotDesign/BotDesign && uvicorn backend.main:app --host 0.0.0.0 --port 8000


3. 資料庫設置
步驟 1：啟用 pgvector 擴展

CREATE EXTENSION IF NOT EXISTS vector;

步驟 2：建立資料表

-- 記憶資料表

CREATE TABLE xiaochenguang_memories (

  id BIGSERIAL PRIMARY KEY,

  conversation_id TEXT,

  user_message TEXT,

  assistant_message TEXT,

  embedding VECTOR(1536),

  memory_type TEXT,

  platform TEXT,

  document_content TEXT,

  created_at TIMESTAMPTZ DEFAULT NOW(),

  access_count INTEGER DEFAULT 1,

  importance_score FLOAT,

  file_name TEXT,

  ai_id TEXT,

  message_type TEXT

);

-- 情緒狀態資料表

CREATE TABLE emotional_states (

  id BIGSERIAL PRIMARY KEY,

  user_id TEXT,

  emotion_type TEXT,

  intensity FLOAT,

  context TEXT,

  timestamp TIMESTAMPTZ DEFAULT NOW()

);

-- 建立索引

CREATE INDEX idx_conversation_id ON xiaochenguang_memories(conversation_id);

CREATE INDEX idx_memory_type ON xiaochenguang_memories(memory_type);

CREATE INDEX idx_user_id ON emotional_states(user_id);

步驟 3：建立 RPC 函數

CREATE OR REPLACE FUNCTION match_memories(

  query_embedding vector(1536),

  match_count int,

  conversation_id text

)

RETURNS TABLE (

  id bigint,

  user_message text,

  assistant_message text,

  similarity float

)

LANGUAGE plpgsql

AS $$

BEGIN

  RETURN QUERY

  SELECT

    m.id,

    m.user_message,

    m.assistant_message,

    1 - (m.embedding <=> query_embedding) AS similarity

  FROM xiaochenguang_memories m

  WHERE m.conversation_id = match_memories.conversation_id

    AND m.memory_type = 'conversation'

  ORDER BY m.embedding <=> query_embedding

  LIMIT match_count;

END;

$$;


🛠 開發指南
本地開發環境設置
1. 安裝依賴
後端：

cd BotDesign/BotDesign

pip install -r backend/requirements.txt

前端：

cd BotDesign/BotDesign/frontend

npm install
2. 配置環境變數
後端 .env：

OPENAI_API_KEY=sk-proj-xxxxx

SUPABASE_URL=https://xxxxx.supabase.co

SUPABASE_ANON_KEY=eyJhbGciOi...

前端 .env：

VITE_API_URL=http://localhost:8000
3. 啟動開發伺服器
後端：

cd BotDesign/BotDesign

uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

前端：

cd BotDesign/BotDesign/frontend

npm run dev


常見開發任務
新增情緒類型
編輯 modules/emotion_detector.py
在 emotion_dictionary 新增條目：

"excited": {

    "keywords": ["興奮", "激動", "刺激"],

    "patterns": [r"好興奮", r"超刺激"],

    "intensity_multipliers": {"超級": 1.5}

}

在 response_styles 新增回應風格
更新前端情緒圖示映射
調整 AI 人格
編輯 profile/user_profile.json
修改 core_traits 數值（0-1）
新增或修改 language_patterns
重啟後端服務
新增 API 端點
在 backend/ 建立新路由檔案
定義 Pydantic 模型：

class NewRequest(BaseModel):

    field1: str

    field2: int

實作路由處理器：

@router.post("/new-endpoint")

async def new_handler(request: NewRequest):

    # 處理邏輯

    return {"result": "success"}

在 main.py 註冊路由：

app.include_router(new_router, prefix="/api")


測試指南
單元測試
測試情感檢測：

from modules.emotion_detector import EnhancedEmotionDetector

detector = EnhancedEmotionDetector()

result = detector.analyze_emotion("我今天超級開心！")

assert result["dominant_emotion"] == "joy"

assert result["intensity"] > 0.7

測試記憶系統：

from modules.memory_system import MemorySystem

memory_system = MemorySystem(supabase, openai_client, "test_table")

await memory_system.save_memory(

    conversation_id="test_123",

    user_input="測試訊息",

    bot_response="測試回應",

    emotion_analysis={"dominant_emotion": "neutral", "intensity": 0.5}

)
整合測試
API 端點測試：

# 測試聊天端點

curl -X POST http://localhost:8000/api/chat \

  -H "Content-Type: application/json" \

  -d '{

    "user_message": "你好",

    "conversation_id": "test_123",

    "user_id": "user_test"

  }'

# 測試記憶端點

curl http://localhost:8000/api/memories/test_123?limit=5


效能優化建議
1. 資料庫查詢優化
使用資料表索引加速查詢
限制記憶召回數量（預設 3-5 條）
實施記憶過期機制（刪除舊記憶）
2. 向量搜尋優化
# 使用 IVFFlat 索引加速向量搜尋

CREATE INDEX ON xiaochenguang_memories 

USING ivfflat (embedding vector_cosine_ops)

WITH (lists = 100);
3. 快取策略
from functools import lru_cache

@lru_cache(maxsize=100)

def get_personality_prompt(emotion_style):

    # 快取人格提示詞生成結果

    return soul.generate_personality_prompt(emotion_style)
4. 非同步處理
# 使用 asyncio 並行處理

async def chat_handler(request):

    # 並行執行記憶召回與歷史獲取

    memories, history = await asyncio.gather(

        memory_system.recall_memories(request.user_message),

        memory_system.get_conversation_history(request.conversation_id)

    )


📊 監控與日誌
日誌系統
後端日誌配置：

logging.basicConfig(

    level=logging.INFO,

    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',

    handlers=[

        logging.FileHandler('logs/backend.log'),

        logging.StreamHandler()

    ]

)

日誌級別：

INFO: 一般資訊（請求接收、處理完成）
DEBUG: 除錯資訊（記憶召回內容、情感分析結果）
ERROR: 錯誤訊息（API 呼叫失敗、資料庫錯誤）
關鍵指標監控
建議監控項目：

API 回應時間（目標：< 2 秒）
OpenAI API 呼叫次數（成本控制）
資料庫查詢效能（向量搜尋時間）
記憶存儲增長速度（容量管理）
錯誤率（系統穩定性）


🔒 安全性考量
1. API 金鑰保護
✅ 使用環境變數存儲敏感資訊
✅ 不將 .env 檔案提交到版本控制
✅ 使用 Replit Secrets 管理密鑰
2. 輸入驗證
# 驗證輸入長度

if len(user_message) > 2000:

    raise HTTPException(status_code=400, detail="訊息過長")

# 過濾惡意內容

import re

if re.search(r'<script>', user_message, re.IGNORECASE):

    raise HTTPException(status_code=400, detail="包含不允許的內容")
3. CORS 配置
# 生產環境應限制來源

app.add_middleware(

    CORSMiddleware,

    allow_origins=["https://your-frontend-domain.com"],

    allow_credentials=True,

    allow_methods=["GET", "POST"],

    allow_headers=["*"],

)
4. 資料庫安全
使用參數化查詢防止 SQL 注入
實施 Row Level Security (RLS)
定期備份資料庫


📚 附錄
A. 常見問題 (FAQ)
Q1: 為什麼記憶召回沒有結果？

檢查 Supabase 是否啟用 pgvector 擴展
確認 match_memories RPC 函數已建立
驗證 OPENAI_API_KEY 是否有效

Q2: 前端無法連接後端？

確認 VITE_API_URL 環境變數設置正確
檢查 CORS 配置是否允許前端域名
驗證後端服務是否正常運行（訪問 /health）

Q3: 如何重置 AI 人格？

-- 刪除人格記憶

DELETE FROM xiaochenguang_memories 

WHERE memory_type = 'personality' 

  AND conversation_id = 'your_conversation_id';

Q4: 如何增加記憶召回數量？

# 修改 chat_router.py

recalled_memories = await memory_system.recall_memories(

    request.user_message,

    request.conversation_id,

    limit=5  # 原本是 3

)


B. 術語表
術語
說明
向量嵌入 (Embedding)
將文本轉換為高維度數值向量的技術
pgvector
PostgreSQL 的向量相似度搜尋擴展
提示詞工程 (Prompt Engineering)
設計 AI 輸入以獲得期望輸出的技術
情感分析 (Emotion Analysis)
辨識文本中情緒傾向的技術
人格矩陣 (Personality Matrix)
AI 人格特質的數值化表示
記憶召回 (Memory Recall)
從長期記憶中檢索相關資訊的過程



C. 參考資源
官方文件：

FastAPI 文件
Vue 3 文件
OpenAI API 文件
Supabase 文件

相關技術：

pgvector GitHub
Text Embedding 3 模型


📝 更新日誌
v1.0.0 (2025-10-15)
✅ 完成從 Telegram Bot 到 Web 版本的遷移
✅ 實現向量記憶系統
✅ 整合情感檢測引擎
✅ 部署到 Replit + Cloudflare Pages
✅ 新增健康檢查按鈕功能
✅ 完成專案文件撰寫



文件版本： v1.0
最後更新： 2025-10-15
維護者： XiaoChenGuang AI Soul Team
聯絡方式： 專案 GitHub

