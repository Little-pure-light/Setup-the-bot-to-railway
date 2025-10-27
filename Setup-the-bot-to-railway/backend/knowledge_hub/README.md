# 知識庫模組 (Knowledge Hub)

## 📝 模組說明

知識庫模組是全域共享資料層，負責知識的結構化儲存與快速檢索。

## 🎯 主要功能

### 1. 知識索引
- 結構化儲存知識條目
- 建立語義關聯網絡

### 2. 知識檢索
- 支援關鍵字搜尋
- 支援語義相似度搜尋

### 3. 知識更新
- 定期更新知識索引
- 清理過時知識

## 🔧 配置選項

- `index_update_interval`: 索引更新間隔（秒）
- `max_knowledge_entries`: 最大知識條目數

## 📡 使用範例

```python
# 索引知識
data = {
    "operation": "index_knowledge",
    "knowledge_id": "k001",
    "content": "Python 是一種程式語言",
    "metadata": {"category": "技術"}
}

# 搜尋知識
data = {
    "operation": "search_knowledge",
    "query": "Python"
}
```
