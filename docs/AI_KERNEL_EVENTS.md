# Kernel 事件與前端協議

Kernel 產生 `KernelEvent`，Router 轉為既有前端協議（**不改協議**）：

| KernelEvent.type | 前端 |
|------------------|------|
| `content` | 純文字 token |
| `tool_status` | `__XCG_EVENT__` + JSON |
| `usage` | `__XCG_META__` + JSON |

Meta 可含：`usage`, `tools_used`, `speech_text`, `voice_mode`, `car_mode`, `kernel`, `trace_id`。
