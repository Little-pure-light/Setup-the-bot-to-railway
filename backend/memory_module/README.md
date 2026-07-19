# Memory Module（CoreController 適配層）

實際記憶邏輯統一在 `modules/memory_system.py` 的 **MemorySystem**。

本目錄只提供：
- 模組註冊與健康檢查
- 將 CoreController 的 `process()` 呼叫轉發給 MemorySystem

## 單一記憶系統

| 層級 | 技術 | 職責 |
|------|------|------|
| 長期 | Supabase + embeddings | 對話永久儲存、向量召回 |
| 短期 | Redis / Mock | `conv:{id}:latest` 最新一輪快取 |

請勿再新增平行的 MemoryCore / 第二套 store 路徑。
