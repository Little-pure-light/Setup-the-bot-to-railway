# Kernel 遷移與 Feature Flags

## Flags

| 變數 | 預設 | 說明 |
|------|------|------|
| `AI_KERNEL_ENABLED` | false | true 時 /api/chat 走 Kernel |
| `AI_KERNEL_SHADOW_MODE` | false | true 且 enabled=false：背景跑 Kernel，無副作用 |
| `KERNEL_FALLBACK_TO_LEGACY` | true | Kernel 致命錯誤回退 Legacy（非 stream 中途） |
| `KERNEL_DEBUG_ENABLED` | false | Debug API |

## 建議 rollout

1. Staging：`SHADOW_MODE=true` 觀察 log  
2. Staging：`ENABLED=true` + 監控  
3. Production：先 shadow，再小流量 enabled  
4. Legacy 在 P2 **不得刪除**

## 回滾

設 `AI_KERNEL_ENABLED=false` 立即回到 Legacy，無需改碼。
