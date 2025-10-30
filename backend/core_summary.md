# XiaoChenGuang AI - 核心架構摘要
# Core Architecture Summary

**版本**: v2.0.0  
**架構**: Phase 2 - 五大模組系統  
**設計理念**: 樂高式掛載 + 反推果因法則

---

## 🏗️ 系統架構總覽

```
┌─────────────────────────────────────────────────────────────┐
│                      用戶層 (User Layer)                      │
│                    ChatInterface.vue                          │
└──────────────────┬──────────────────────────────────────────┘
                   │ HTTP Request
                   ↓
┌─────────────────────────────────────────────────────────────┐
│                    API 層 (API Layer)                         │
│                  FastAPI + Router System                      │
│  ┌──────────────┬──────────────┬──────────────────────────┐ │
│  │ chat_router  │ memory_router │ healthcheck_router       │ │
│  └──────────────┴──────────────┴──────────────────────────┘ │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ↓
┌─────────────────────────────────────────────────────────────┐
│              核心控制層 (Core Controller Layer)               │
│                     CoreController                            │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  模組註冊 │ 動態載入 │ 統一通信 │ 健康監控            │   │
│  └──────────────────────────────────────────────────────┘   │
└──────┬─────────┬──────────┬──────────┬──────────────────────┘
       │         │          │          │
       ↓         ↓          ↓          ↓
┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
│ Memory  │ │Reflection│ │Knowledge│ │Behavior │
│ Module  │ │ Module  │ │  Hub    │ │ Module  │
│  (1)    │ │   (2)   │ │   (3)   │ │   (4)   │
└────┬────┘ └────┬────┘ └─────────┘ └─────────┘
     │           │
     ↓           ↓
┌─────────────────────────────────────────────┐
│          資料層 (Data Layer)                 │
│  ┌────────────┐    ┌──────────────────┐    │
│  │   Redis    │    │    Supabase      │    │
│  │ (短期記憶)  │    │   (長期記憶)     │    │
│  └────────────┘    └──────────────────┘    │
└─────────────────────────────────────────────┘
```

---

## 🔄 資料流動關係圖

### 主流程：對話處理 + 記憶儲存 + 反思分析

```
   [使用者發送訊息]
          │
          ↓
   ┌─────────────────┐
   │  /api/chat      │  ← chat_router.py
   │  接收請求       │
   └────────┬────────┘
            │
            ↓
   ┌─────────────────────────┐
   │  1. 記憶檢索             │
   │  MemorySystem.recall()  │  ← 現有系統
   └────────┬────────────────┘
            │
            ↓
   ┌─────────────────────────┐
   │  2. Prompt 構建          │
   │  PromptEngine.build()   │  ← 現有系統
   └────────┬────────────────┘
            │
            ↓
   ┌─────────────────────────┐
   │  3. AI 生成回覆          │
   │  OpenAI GPT-4o-mini     │
   └────────┬────────────────┘
            │
            ↓
   ┌─────────────────────────┐
   │  4. 儲存記憶             │
   │  MemorySystem.save()    │  ← 現有系統
   └────────┬────────────────┘
            │
            ├─────────────────────────────────────────┐
            │                                         │
            ↓                                         ↓
   ┌────────────────────┐                  ┌────────────────────┐
   │  5A. 反思分析       │                  │  5B. 新記憶模組     │
   │  ReflectionModule  │                  │  MemoryCore        │
   │  .process()        │                  │  .store_conversation()│
   └────────┬───────────┘                  └────────┬───────────┘
            │                                       │
            │  ┌────────────────────────────────────┤
            │  │                                    │
            ↓  ↓                                    ↓
   ┌─────────────────┐                    ┌────────────────────┐
   │  反推果因分析    │                    │  Token 化處理       │
   │  - 觀察層       │                    │  TokenizerEngine   │
   │  - 因果層(L1/L2/L3)│                 └────────┬───────────┘
   │  - 改進層       │                             │
   │  - 元認知層     │                             ↓
   └────────┬────────┘                    ┌────────────────────┐
            │                             │  雙層儲存           │
            │                             │  ├─ Redis (短期)   │
            │                             │  └─ Supabase (長期)│
            │                             └────────────────────┘
            │
            ↓
   ┌─────────────────────────┐
   │  6. 回寫記憶             │
   │  MemoryCore.store(       │
   │     reflection=...       │
   │  )                      │
   └────────┬────────────────┘
            │
            ↓
   ┌─────────────────────────┐
   │  7. 回傳結果             │
   │  ChatResponse{          │
   │    assistant_message,   │
   │    emotion_analysis,    │
   │    reflection ← 新增！   │
   │  }                      │
   └─────────────────────────┘
```

---

## 📦 模組詳細說明

### 1️⃣ 記憶模組 (Memory Module)

**位置**: `backend/modules/memory/`

**核心職責**: AI 數字宇宙的中樞神經資料層

**架構分層**:

```
MemoryCore (核心控制器)
    │
    ├─→ TokenizerEngine (Token 化引擎)
    │   ├─ tiktoken 主方案
    │   └─ UTF-8 bytes 降級方案
    │
    ├─→ RedisInterface (短期記憶接口)
    │   ├─ Key: conv:{id}:latest
    │   ├─ TTL: 172800 秒 (2天)
    │   └─ 待刷寫隊列管理
    │
    └─→ SupabaseInterface (長期記憶接口)
        ├─ 表: xiaochenguang_memories
        ├─ 欄位映射機制
        └─ 批次寫入優化
```

**資料結構**:

```json
{
  "conversation_id": "conv_001",
  "user_id": "user_123",
  "user_message": "你好，小宸光！",
  "assistant_message": "你好！很高興見到你！",
  "token_data": {
    "user": [2103, 188, 420, ...],
    "assistant": [2103, 188, ...],
    "reflection": [5678, 9012, ...],
    "method": "tiktoken",
    "encoding": "cl100k_base",
    "total_count": 42
  },
  "reflection": {...},
  "cid": null,
  "created_at": "2025-10-19T12:00:00Z"
}
```

**關鍵特性**:
- ✅ 雙層記憶架構（短期 + 長期）
- ✅ Token 數字化儲存
- ✅ 自動降級機制
- ✅ 批次刷寫優化

---

### 2️⃣ 反思模組 (Reflection Module)

**位置**: `backend/reflection_module/`

**核心職責**: 反推果因法則引擎，執行元認知分析

**設計哲學**:
> 不是問「為什麼我這樣回答」，而是問「什麼原因導致我必須這樣回答」

**四層分析架構**:

```
┌────────────────────────────────────────┐
│  1. 觀察層 (Observation Layer)          │
│  ─────────────────────────────────     │
│  分析回答的表面特徵：                   │
│  - 長度、結構、範例、情感詞彙等          │
└────────────────┬───────────────────────┘
                 │
                 ↓
┌────────────────────────────────────────┐
│  2. 因果層 (Causal Layer)               │
│  ─────────────────────────────────     │
│  三層反推：                             │
│  - L1 直接原因 (表面症狀)               │
│  - L2 間接原因 (中層機制)               │
│  - L3 系統性原因 (深層結構)             │
└────────────────┬───────────────────────┘
                 │
                 ↓
┌────────────────────────────────────────┐
│  3. 改進層 (Improvement Layer)          │
│  ─────────────────────────────────     │
│  基於因果分析生成具體可執行的改進策略    │
└────────────────┬───────────────────────┘
                 │
                 ↓
┌────────────────────────────────────────┐
│  4. 元認知層 (Meta-Cognitive Layer)     │
│  ─────────────────────────────────     │
│  評估反思本身的質量與置信度              │
└────────────────────────────────────────┘
```

**因果模式庫** (5 種核心模式):

1. **insufficient_detail** - 內容不足
2. **structural_weakness** - 結構薄弱
3. **emotional_disconnect** - 情感脫節
4. **contextual_fragmentation** - 上下文斷裂
5. **depth_mismatch** - 深度失衡

**反思輸出範例**:

```json
{
  "summary": "🔍 核心發現：回應長度不足（9 字）：可能對問題理解不夠深入。已進行 3 層因果分析，提出 3 項改進方向。",
  "causes": [
    "【L1-直接】回應長度不足（9 字）：可能對問題理解不夠深入",
    "【L2-間接】資訊檢索不充分：未調用足夠的記憶或知識",
    "【L3-系統】保守策略主導：為避免錯誤而選擇最小化回應"
  ],
  "improvements": [
    "💡 內容增強：添加 2-3 個具體範例或場景模擬",
    "📚 記憶整合：優先檢索與問題相關的歷史對話",
    "📐 結構化：採用「觀點-證據-結論」三段論"
  ],
  "confidence": 0.72,
  "meta_analysis": {
    "query_complexity": "low",
    "response_quality_score": 0.3,
    "emotion_alignment": 0.3,
    "causal_depth": 3
  }
}
```

**關鍵特性**:
- ✅ 多層級因果分析
- ✅ 具體可執行的改進建議
- ✅ 置信度量化
- ✅ 元認知自我評估

---

### 3️⃣ 知識庫模組 (Knowledge Hub)

**位置**: `backend/knowledge_hub/`

**核心職責**: 結構化知識儲存與語義搜尋

**狀態**: 基礎框架已建立，待 Phase 3 完整實現

---

### 4️⃣ 行為調節模組 (Behavior Module)

**位置**: `backend/behavior_module/`

**核心職責**: 動態人格向量調整與情感適應

**人格向量**:
```json
{
  "empathy": 0.5,
  "curiosity": 0.5,
  "humor": 0.51,
  "technical_depth": 0.51
}
```

**狀態**: 基礎框架已建立，待 Phase 3 與反思模組深度整合

---

## 🔌 模組通信機制

### CoreController 統一調度

所有模組通過 CoreController 進行通信，避免直接依賴：

```python
# 錯誤方式 ❌
from backend.reflection_module import ReflectionModule
reflection = ReflectionModule()

# 正確方式 ✅
from backend.core_controller import get_core_controller

controller = await get_core_controller()
reflection_module = await controller.get_module("reflection")
result = await reflection_module.process(data)
```

### 資料流通標準

所有模組遵循統一的輸入/輸出格式：

**輸入**:
```json
{
  "operation": "operation_name",  // 可選
  "...": "data fields"
}
```

**輸出**:
```json
{
  "success": true/false,
  "data": {...},
  "error": "..." // 失敗時
}
```

---

## 🔄 批次刷寫機制

### Memory Flush Worker

**位置**: `backend/jobs/memory_flush_worker.py`

**工作流程**:

```
每 5 分鐘 (可配置)
    │
    ↓
獲取 Redis 待刷寫隊列 (最多 100 筆)
    │
    ↓
批次寫入 Supabase
    │
    ├─ 成功 → 從隊列移除
    │
    └─ 失敗 → 重試 (最多 3 次)
          │
          └─ 指數退避 (1s, 2s, 4s)
```

**啟動方式**:

```python
from backend.jobs.memory_flush_worker import create_flush_worker
from backend.modules.memory.core import MemoryCore

memory = MemoryCore()
worker = create_flush_worker(memory, interval_seconds=300)

await worker.start()
```

---

## 🏥 健康檢查系統

### 三層健康檢查

#### 1. 基本健康檢查
**端點**: `GET /api/health`

**回傳**:
```json
{
  "status": "healthy",
  "service": "XiaoChenGuang AI System",
  "version": "2.0.0"
}
```

#### 2. 模組健康檢查
**端點**: `GET /api/health/modules`

**回傳**:
```json
{
  "status": "success",
  "data": {
    "controller": "healthy",
    "total_modules": 4,
    "enabled_modules": 4,
    "modules": {
      "memory": "healthy",
      "reflection": "healthy",
      "knowledge": "healthy",
      "behavior": "healthy"
    }
  }
}
```

#### 3. 詳細健康檢查
**端點**: `GET /api/health/detailed`

**回傳**: 包含環境變數、模組狀態、配置資訊的完整報告

---

## 🔐 安全性設計

### 錯誤隔離

模組失敗不影響主流程：

```python
try:
    # 新模組處理
    reflection_result = await reflection_module.process(...)
except Exception as e:
    logger.warning(f"模組處理失敗（不影響主流程）: {e}")
    # 主流程繼續
```

### 降級方案

每個關鍵組件都有降級方案：

- **tiktoken 不可用** → UTF-8 bytes
- **Redis 不可用** → Redis Mock
- **反思模組失敗** → reflection 欄位返回 null

---

## 📊 效能優化

### 非同步處理

所有 I/O 操作使用 async/await：

```python
async def process(...):
    result = await module.process(data)
    return result
```

### 批次操作

- Redis 批次讀取/寫入
- Supabase 批次 upsert
- Token 化批次處理

### 快取策略

- 短期記憶 Redis 快取（2天 TTL）
- 模組單例模式
- 配置文件快取

---

## 🎯 設計原則

### 1. 樂高式掛載

每個模組都是獨立的「樂高積木」：

- ✅ 可獨立啟用/停用
- ✅ 配置文件熱更新
- ✅ 不破壞現有功能
- ✅ 松耦合設計

### 2. 向後兼容

所有新功能都保持向後兼容：

- ✅ 現有 API 格式不變
- ✅ 新欄位為可選 (Optional)
- ✅ 失敗不影響主流程

### 3. 數據為王

一切以 Token 數字化為核心：

- ✅ 文字 → Token 序列
- ✅ 長期儲存以 Token 為主
- ✅ 文字可選性保留

### 4. 元認知驅動

AI 能夠反思自己的回答：

- ✅ 從「果」反推「因」
- ✅ 多層級分析
- ✅ 自我改進

---

## 🚀 未來擴展

### Phase 3 規劃

1. **IPFS 整合**
   - CID 索引實現
   - 去中心化儲存

2. **QLoRA 微調**
   - 啟用 FineTune Module
   - 基於記憶的持續學習

3. **完整反思循環**
   - 反思 → 行為調節 → 人格更新
   - 閉環學習機制

4. **知識圖譜**
   - 語義網絡建構
   - 知識推理引擎

---

## 📚 相關文檔

- [記憶模組文檔](modules/memory/README.md)
- [反思模組配置](reflection_module/config.json)
- [測試報告](../logs/module_test_results.md)
- [資料庫設定](../others/DATABASE_SETUP.md)

---

**文檔版本**: 1.0  
**最後更新**: 2025-10-19  
**架構狀態**: ✅ Phase 2 完成
