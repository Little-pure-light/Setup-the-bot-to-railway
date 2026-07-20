# Kernel Debug Trace

## 原則

只記錄：stage 名稱、duration_ms、status、counts、error_code  
**不記錄**：完整 prompt、完整記憶、對話全文、tool secret

## API

必須**同時**：

1. `KERNEL_DEBUG_ENABLED=true`
2. Bearer = `KERNEL_DEBUG_SECRET` 或 `API_SECRET`（**至少一個必須設定**，否則 404）

- `GET /api/kernel/debug/traces`
- `GET /api/kernel/debug/traces/{trace_id}`

未授權 → 401；flag 關 / 無 secret → **404**（不洩漏端點存在）。

## 存儲

進程內最近約 200 筆；重啟消失。Shadow 模式不寫入 trace。
