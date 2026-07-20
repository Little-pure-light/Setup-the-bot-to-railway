# AI Kernel Pipeline Stages

順序：

1. **budget** — 日預算檢查  
2. **moderation** — 輸入審核  
3. **load_context_sources** — 記憶召回、歷史、附件（失敗降級空字串）  
4. **build_prompt** — PromptPort（人格/情緒）  
5. **plan** — RulePlanner（無額外 LLM）  
6. **strategy** — 語音/車載/預設 max_tokens  
7. **assemble_context** — Token budget 裁剪  
8. **generate** — AgentLoop 或直接 complete / stream  
9. **post_process_plan** — 建立冪等 job；shadow 不寫入  

## Context Budget

- `KERNEL_CONTEXT_TOKEN_BUDGET`（預設 12000，粗估字元/2）
- `system_safety` 與 `user_message` 為 required，不可裁掉
- 記憶去重後再放入

## Agent Loop 限制

| 參數 | 預設 |
|------|------|
| max_iterations | 3 |
| max_tools_per_turn | 5 |
| max_total_tool_seconds | 30 |
| max_tool_output_chars | 12000（registry 環境變數） |
