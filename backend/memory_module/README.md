# 記憶模組 (Memory Module)

## 📝 模組說明

記憶模組是小宸光系統的核心資料層，負責：
- 短期記憶（Redis 緩存）
- 長期記憶（Supabase 資料庫）
- 文字 Token 化處理
- 記憶召回與檢索

## 🎯 主要功能

### 1. 對話儲存
- 自動將對話內容 Token 化
- 儲存至 Redis 作為短期記憶（24小時）
- 同步至 Supabase 作為長期記憶

### 2. 記憶召回
- 從 Redis 快速召回最近對話
- 支援語義搜尋（向量相似度）

### 3. Token 化
- 使用 tiktoken 進行精確 Token 計數
- 支援字元數估算備援方案

## 🔧 配置選項

參考 `config.json`:
- `redis_ttl`: Redis 緩存過期時間（秒）
- `max_token_length`: 最大 Token 長度限制
- `embedding_model`: 向量化模型名稱

## 📡 API 接口

### 儲存對話
```python
data = {
    "operation": "store_conversation",
    "conversation_id": "conv_001",
    "user_message": "你好",
    "assistant_message": "你好！",
    "reflection": "回應適當"
}
```

### 召回記憶
```python
data = {
    "operation": "retrieve_memory",
    "conversation_id": "conv_001"
}
```
