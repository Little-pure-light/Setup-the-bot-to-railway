# AI Kernel 架構

## 目標

將 `backend/chat_router.py` 中的業務流程漸進拆為可測試、可替換的 **AI Kernel**，並以 Strangler Pattern 保持 Legacy 可用。

## 架構圖

```text
┌─────────────┐
│  FastAPI    │  /api/chat  （公開 API 不變）
│ chat_router │
└──────┬──────┘
       │ AI_KERNEL_ENABLED?
       ├─ false ──► Legacy Flow（完整保留）
       └─ true  ──► AIKernel
                      │
         ┌────────────┼────────────────┐
         ▼            ▼                ▼
   RequestPipeline  Planner      ResponseStrategy
         │            │                │
         ▼            ▼                ▼
   ContextBuilder  AgentLoop      ModelGateway
         │         ToolPolicy      (OpenAI only)
         ▼            │
   PostProcess ◄──────┘
   (idempotent)
```

## 目錄

```text
backend/ai_kernel/
  kernel.py           # 入口
  models.py           # KernelRequest/Result/Plan/...
  context.py          # ContextBuilder
  pipeline.py         # RequestPipeline
  feature_flags.py
  tracing.py
  errors.py
  ports.py / adapters.py
  planner/rule_planner.py
  model_gateway/openai_gateway.py
  tool_policy/agent_loop.py
  strategies/response.py
  post_process.py
  debug_router.py
```

## 依賴規則

| 層 | 允許 | 禁止 |
|----|------|------|
| Kernel 核心 | ports 抽象、Pydantic 模型 | FastAPI Request、OpenAI SDK、全域 Supabase/Redis |
| Adapters | 呼叫既有 modules | 被 Kernel 反向硬依賴 |
| Gateway | OpenAI SDK（僅此處） | 被 Router 直接呼叫模型 |

## 資料模型

- `KernelRequest` / `KernelContext` / `KernelResult`
- `Plan` / `PlanStep` / `ModelConfig` / `ResponseStrategy`
- `PostProcessJob` / `KernelEvent` / `ContextBlock`
