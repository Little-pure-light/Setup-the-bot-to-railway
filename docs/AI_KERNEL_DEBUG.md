# Kernel Debug Trace

## 原則

只記錄：stage 名稱、duration_ms、status、counts、error_code  
**不記錄**：完整 prompt、完整記憶、對話全文、tool secret

## API

需 `KERNEL_DEBUG_ENABLED=true`，且若設定了 `API_SECRET` 需 Bearer。

- `GET /api/kernel/debug/traces`
- `GET /api/kernel/debug/traces/{trace_id}`

## 存儲

進程內最近約 200 筆；重啟消失。
