# 第二階段進度：AI Kernel Pipeline

| 任務 | 狀態 | Commit | 備註 |
|------|------|--------|------|
| P2-01 Kernel 基礎模型與介面 | 完成 | `7fc5a75` | models/errors/flags/ports |
| P2-02 Request Pipeline | 完成 | `0d42eec` | pipeline.py |
| P2-03 Context Builder | 完成 | `0d42eec` | budget + dedupe |
| P2-04 Model Gateway | 完成 | `4769924` | OpenAI only |
| P2-05 Planner | 完成 | `4769924` | RulePlanner |
| P2-06 Tool Policy / Agent Loop | 完成 | `4769924` | 硬上限 |
| P2-07 Response Strategy | 完成 | `4769924` | voice/car |
| P2-08 Post-Processing | 完成 | `4769924` | idempotent |
| P2-09 Debug Trace | 完成 | `5c5a4fb` | debug_router |
| P2-10 Feature Flag 與遷移 | 完成 | `5be39a9` | strangler in chat_router |
| P2-11 測試與 Parity | 完成 | `c2d86da` | unit + integration |
| P2-12 文件 | 完成 | `b4b6abc` | docs/AI_KERNEL_* |

## 切換

- 預設 Legacy：`AI_KERNEL_ENABLED=false`
- Kernel：`AI_KERNEL_ENABLED=true`
- Shadow：`AI_KERNEL_SHADOW_MODE=true`（且 enabled=false）
- 致命錯誤回退：`KERNEL_FALLBACK_TO_LEGACY=true`（預設）

## 不變更

- `/api/chat` 公開契約
- Streaming 前端協議 `__XCG_EVENT__` / `__XCG_META__`
- Legacy Flow 完整保留
- 資料庫 Schema
