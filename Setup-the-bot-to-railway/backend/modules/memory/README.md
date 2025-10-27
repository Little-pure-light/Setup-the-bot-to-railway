# 記憶模組（Memory Module）

> AI 數字宇宙的中樞神經資料層

## 📘 模組用途

記憶模組是小宸光 AI 系統的核心數據層，負責：

1. **對話紀錄數字化**：使用 Token 化技術將所有文字轉換為數字序列
2. **雙層記憶架構**：
   - **短期記憶**：Redis 快取（2天 TTL）
   - **長期記憶**：Supabase 永久儲存
3. **反思紀錄索引**：儲存 AI 的自我反思結果
4. **IPFS 整合**：（預留）未來支援去中心化儲存
5. **統一資料介面**：供所有模組調用的標準 API

## 🏗️ 架構設計

```
Memory Module
├── tokenizer.py          # Token 化引擎（tiktoken + 降級方案）
├── io_contract.py        # I/O 合約層（資料校驗與標準化）
├── redis_interface.py    # Redis 短期記憶接口
├── supabase_interface.py # Supabase 長期記憶接口
├── core.py              # 記憶核心控制器
└── config.json          # 模組配置
```

## 🔧 環境變數

### 必要變數

```bash
# Supabase 配置（已在專案中設定）
SUPABASE_URL=your_supabase_url
SUPABASE_ANON_KEY=your_supabase_key

# Redis 配置（可選，未設定則使用 Mock）
REDIS_URL=redis://:password@host:6379/0
```

### 可選變數

```bash
# Token 化配置
TOKENIZER_NAME=cl100k_base

# Redis TTL 設定（秒）
MEMORY_REDIS_TTL_SECONDS=172800  # 預設 2 天

# 批次刷寫大小
MEMORY_FLUSH_BATCH_SIZE=100

# 資料表映射（JSON 格式）
MEMORY_TABLE_MAP='{"conversations":"xiaochenguang_memories","reflections":"xiaochenguang_reflections"}'
```

## 📊 資料表結構

### xiaochenguang_memories（對話記憶表）

| 欄位 | 類型 | 說明 |
|------|------|------|
| id | uuid | 主鍵 |
| conversation_id | text | 對話 ID |
| user_id | text | 使用者 ID |
| user_message | text | 使用者訊息（可選） |
| assistant_message | text | AI 回覆（可選） |
| reflection | jsonb | 反思結果 |
| token_data | jsonb | **Token 資料（核心）** |
| cid | text | IPFS 索引（選用） |
| created_at | timestamptz | 建立時間 |
| importance_score | float | 重要性評分 |
| access_count | int | 存取次數 |

### token_data 結構

```json
{
  "user": [1234, 5678, 9012],
  "assistant": [3456, 7890, 1234],
  "reflection": [5678, 9012],
  "method": "tiktoken",
  "encoding": "cl100k_base",
  "total_count": 9,
  "timestamp": "2025-10-19T12:00:00"
}
```

## 🔌 欄位映射配置

如果現有資料表欄位名稱不同，可在 `config.json` 中設定映射：

```json
{
  "columns_map": {
    "conversation_id": "conv_id",
    "user_message": "user_msg",
    "assistant_message": "ai_response"
  }
}
```

## 💻 使用方式

### 1. 基本使用

```python
from backend.modules.memory.core import MemoryCore

# 初始化
memory = MemoryCore()

# 儲存對話
result = memory.save_chat(
    user_message="你好，小宸光！",
    assistant_message="你好！很高興見到你！",
    conversation_id="conv_001",
    user_id="user_123"
)

# 讀取上下文
context = memory.load_recent_context("conv_001")
```

### 2. 整合到聊天路由

在 `chat_router.py` 中添加（不改變 API）：

```python
from backend.modules.memory.core import MemoryCore

memory_core = MemoryCore()

# 在生成回覆後
memory_core.store_conversation(
    conversation_id=request.conversation_id,
    user_id=request.user_id,
    user_msg=user_message,
    assistant_msg=assistant_message,
    reflection=reflection_obj
)
```

### 3. 儲存反思

```python
result = memory.save_reflection(
    reflection_text={
        "summary": "回應過於簡短",
        "causes": ["缺少實例", "未深入解釋"],
        "improvements": ["增加範例", "提供更多細節"]
    },
    conversation_id="conv_001",
    user_id="user_123"
)
```

## 🧪 本地測試步驟

### 1. Token 化測試

```python
from backend.modules.memory.tokenizer import TokenizerEngine

tokenizer = TokenizerEngine()
tokens = tokenizer.tokenize_text("測試文字")
print(f"Token 數量: {len(tokens)}")
```

### 2. Redis 快取測試

```python
from backend.modules.memory.redis_interface import RedisInterface

redis = RedisInterface()
redis.store_short_term("test_conv", {"test": "data"})
data = redis.load_recent_context("test_conv")
```

### 3. Supabase 儲存測試

```python
from backend.modules.memory.supabase_interface import SupabaseInterface

supabase = SupabaseInterface()
result = supabase.store_single_memory({
    "conversation_id": "test_001",
    "user_id": "user_123",
    "token_data": {"user": [1,2,3]},
    "created_at": "2025-10-19T12:00:00"
})
```

### 4. 完整流程測試

```python
from backend.modules.memory.core import MemoryCore

memory = MemoryCore()

# 儲存對話
result = memory.save_chat(
    user_message="測試",
    assistant_message="收到",
    conversation_id="test_conv",
    user_id="test_user"
)

print(f"Redis: {result['redis_stored']}")
print(f"Supabase: {result['supabase_stored']}")
print(f"Token 數: {result['token_count']}")
```

## 🔄 批次刷寫機制

記憶模組支援自動批次刷寫：

### 啟動刷寫工作器

```python
from backend.jobs.memory_flush_worker import create_flush_worker
from backend.modules.memory.core import MemoryCore

memory = MemoryCore()
worker = create_flush_worker(memory, interval_seconds=300)

# 啟動
await worker.start()
```

### 手動觸發刷寫

```python
result = await worker.manual_flush()
print(f"刷寫 {result['flushed_count']} 筆記錄")
```

## 🛡️ 安全性

1. **資料加密**：text_cache 欄位可設定加密（AES）
2. **IPFS 簽名**：上傳前先做 SHA256 雜湊
3. **存取控制**：所有操作需通過 user_id 驗證

## ⚙️ 啟用/停用模組

編輯 `config.json`：

```json
{
  "enabled": true  // 改為 false 停用
}
```

重啟 Backend workflow 即可。

## 📈 效能優化

- **Redis 非同步**：避免阻塞主線程
- **批次寫入**：減少 Supabase 請求次數
- **Token 壓縮**：使用 jsonb 欄位儲存

## ❌ 常見錯誤與排除

### 1. tiktoken 無法安裝

**症狀**：`ImportError: No module named 'tiktoken'`

**解決**：模組會自動切換到 UTF-8 bytes 降級方案

### 2. Redis 連接失敗

**症狀**：`Redis connection refused`

**解決**：檢查 `REDIS_URL` 或使用內建 Mock

### 3. Supabase 寫入失敗

**症狀**：`Supabase error: column not found`

**解決**：檢查 `columns_map` 設定是否正確

### 4. Token 數量異常

**症狀**：Token 數量為 0 或過大

**解決**：
```python
# 檢查 tokenizer 狀態
print(tokenizer.fallback_mode)
print(tokenizer.tokenizer_name)
```

## 🔗 模組通信

其他模組調用記憶模組的標準方式：

```python
from backend.core_controller import get_core_controller

controller = await get_core_controller()
memory_module = await controller.get_module("memory")

# 呼叫功能
result = await memory_module.process({
    "operation": "save_chat",
    "user_message": "...",
    "assistant_message": "...",
    "conversation_id": "...",
    "user_id": "..."
})
```

## 📚 相關文檔

- [反思模組文檔](../../reflection_module/README.md)
- [核心控制器文檔](../../core_controller.py)
- [資料庫設定指南](../../../others/DATABASE_SETUP.md)

---

**版本**：2.0.0  
**最後更新**：2025-10-19  
**狀態**：✅ 已啟用
