# 第二階段進度：AI Kernel Pipeline

| 任務 | 狀態 | Commit | 備註 |
|------|------|--------|------|
| P2-01 Kernel 基礎模型與介面 | 完成 | （見 log） | models/errors/ports |
| P2-02 Request Pipeline | 完成 | | pipeline.py |
| P2-03 Context Builder | 完成 | | budget + dedupe |
| P2-04 Model Gateway | 完成 | | OpenAI only |
| P2-05 Planner | 完成 | | RulePlanner |
| P2-06 Tool Policy / Agent Loop | 完成 | | 硬上限 |
| P2-07 Response Strategy | 完成 | | voice/car |
| P2-08 Post-Processing | 完成 | | idempotent |
| P2-09 Debug Trace | 完成 | | debug_router |
| P2-10 Feature Flag 與遷移 | 完成 | | chat_router strangler |
| P2-11 測試與 Parity | 完成 | | unit + integration |
| P2-12 文件 | 完成 | | docs/AI_KERNEL_* |

## 切換

- 預設 Legacy：`AI_KERNEL_ENABLED=false`
- Kernel：`AI_KERNEL_ENABLED=true`
- Shadow：`AI_KERNEL_SHADOW_MODE=true`（enabled=false 時）

## 現況分析摘要

見初版分析：chat_router 保留 HTTP/協議；業務可移至 Kernel；Legacy 不刪。
