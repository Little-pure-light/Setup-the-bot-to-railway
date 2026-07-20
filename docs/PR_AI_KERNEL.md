# PR: feature/ai-kernel-pipeline → main

## 任務目標

第二階段：以 Strangler Pattern 引入 **AI Kernel / Request Pipeline**，在不破壞 Legacy 與前端串流協議的前提下，拆分可測試、可回退的對話核心。

## 本輪審核強化（follow-up）

1. **Shadow Mode 禁止任何副作用**  
   - 不寫記憶、不 `budget.record`、不執行真實工具、不持久化 debug trace  
   - `ToolPolicy(shadow=True)` 拒絕暴露/執行工具  

2. **真正多輪 Agent Loop**  
   - `run_tool_rounds`：模型可連續多輪 `tool_calls`，直到 stop 或達 `max_iterations`  
   - 硬上限：iterations / tools / total seconds / output chars  

3. **實際 Tool Policy**  
   - blocklist / 可選 allowlist  
   - 車載/語音預設僅 voice-safe 工具  
   - 與 registry 封鎖名對齊  

4. **工具後最終答案 Token Streaming**  
   - 工具輪次非串流 → 最終 `model.stream(messages)` 逐 token  

5. **Debug API 鎖定**  
   - 必須 `KERNEL_DEBUG_ENABLED` + Bearer（`KERNEL_DEBUG_SECRET` 或 `API_SECRET`）  
   - 無 secret → 404  

6. **測試補齊**  
   - multi-round loop、policy、shadow、stream-after-tools、debug lock  

## 是否影響核心功能

- [x] Streaming（Kernel 路徑協議相容；工具後改為 stream final）
- [x] Tool Calling
- [ ] 記憶格式（否）
- [ ] 公開 API 路徑（否）
- [x] 語音/車載策略（policy 限制工具）

## 切換

```text
AI_KERNEL_ENABLED=false          # 預設 Legacy
AI_KERNEL_ENABLED=true           # Kernel
AI_KERNEL_SHADOW_MODE=true       # 背景 shadow（無副作用）
KERNEL_FALLBACK_TO_LEGACY=true
```

## 回滾

設 `AI_KERNEL_ENABLED=false`；或 revert 本分支、不合併。

## 測試

```text
pytest -q
cd frontend && npm run test && npm run build && npx playwright test --project="Desktop Chrome"
```

## 請 Reviewer 注意

- Legacy 路徑完整保留  
- 未改 DB schema  
- 未引入新模型供應商 / MCP / shell 工具  
