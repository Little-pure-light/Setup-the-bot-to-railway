"""
真正多輪 Agent Loop + Tool Policy。

流程：
  while iteration < max:
    model.complete_with_tools(...)
    if tool_calls: execute (policy 過濾) → append messages → continue
    else: break（有 final content 或需再 stream）
  回傳 messages / tools_used / events；可選 content（非串流時）

串流最終答案由 Kernel.run_stream 在 tools 結束後呼叫 model.stream(messages)。
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from backend.ai_kernel.errors import AgentLoopLimitError
from backend.ai_kernel.models import KernelContext, KernelRequest
from backend.ai_kernel.ports import ModelGatewayPort, ToolExecutorPort
from backend.ai_kernel.tool_policy.policy import ToolPolicy
from backend.ai_kernel.tracing import KernelTrace


class AgentLoop:
    def __init__(
        self,
        model: ModelGatewayPort,
        tools: ToolExecutorPort,
        policy: ToolPolicy,
        trace: Optional[KernelTrace] = None,
    ):
        self.model = model
        self.tools = tools
        self.policy = policy
        self.trace = trace

    async def run_tool_rounds(
        self,
        ctx: KernelContext,
        *,
        user_id: str,
        request: Optional[KernelRequest] = None,
    ) -> Dict[str, Any]:
        """
        只跑工具多輪，不強制 final complete。

        回傳:
          messages, tools_used, usage, events,
          needs_final_generation: bool,
          early_content: str  # 若模型已給最終文字
        """
        req = request or ctx.request
        messages = list(ctx.messages)
        model = ctx.model_config_obj.model
        temperature = ctx.strategy.temperature
        max_tokens = min(1000, ctx.strategy.max_tokens)
        tools_used: List[Dict[str, Any]] = []
        events: List[Dict[str, Any]] = []
        usage_acc = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        allow_plan = bool(ctx.plan and ctx.plan.allow_tools and (req.use_tools if req else True))
        raw_defs = self.tools.openai_definitions() if allow_plan else []
        decision = self.policy.decide_exposure(
            raw_defs, req, allow_tools=allow_plan
        )
        defs = decision.filtered_definitions

        if not decision.allowed or not defs:
            events.append(
                {
                    "type": "tool_status",
                    "status": "skipped",
                    "message": decision.reason
                    if decision.reason != "ok"
                    else "本次無需使用工具",
                    "tools": [],
                }
            )
            return {
                "messages": messages,
                "tools_used": tools_used,
                "usage": usage_acc,
                "events": events,
                "needs_final_generation": True,
                "early_content": "",
            }

        t0 = time.perf_counter()
        iterations = 0
        max_iter = self.policy.max_iterations()
        total_tool_calls = 0

        events.append(
            {
                "type": "tool_status",
                "status": "planning",
                "message": "正在判斷是否需要使用工具…",
                "tools": [],
            }
        )

        while iterations < max_iter:
            iterations += 1
            if time.perf_counter() - t0 > self.policy.max_tool_seconds():
                events.append(
                    {
                        "type": "tool_status",
                        "status": "error",
                        "message": "工具總時限已到，改為直接回答",
                        "tools": [],
                    }
                )
                return {
                    "messages": messages,
                    "tools_used": tools_used,
                    "usage": usage_acc,
                    "events": events,
                    "needs_final_generation": True,
                    "early_content": "",
                    "limit_hit": "max_total_tool_seconds",
                }

            if self.trace:
                self.trace.start(f"agent_iter_{iterations}")

            tool_resp = await self.model.complete_with_tools(
                messages,
                tools=defs,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            self._merge_usage(usage_acc, tool_resp.get("usage") or {})

            if tool_resp.get("finish_reason") == "error":
                events.append(
                    {
                        "type": "tool_status",
                        "status": "error",
                        "message": "工具階段失敗，改為直接回答",
                        "tools": [],
                    }
                )
                if self.trace:
                    self.trace.end(
                        f"agent_iter_{iterations}",
                        status="error",
                        error_code="tool_calling_error",
                    )
                return {
                    "messages": messages,
                    "tools_used": tools_used,
                    "usage": usage_acc,
                    "events": events,
                    "needs_final_generation": True,
                    "early_content": "",
                }

            tool_calls = tool_resp.get("tool_calls") or []
            if tool_resp.get("finish_reason") != "tool_calls" or not tool_calls:
                # 模型決定不再呼叫工具
                content = tool_resp.get("content") or ""
                if iterations == 1 and not tools_used:
                    events.append(
                        {
                            "type": "tool_status",
                            "status": "skipped",
                            "message": "本次無需使用工具",
                            "tools": [],
                        }
                    )
                else:
                    events.append(
                        {
                            "type": "tool_status",
                            "status": "done",
                            "message": "工具階段結束",
                            "tools": [],
                            "step": total_tool_calls,
                            "total": total_tool_calls,
                        }
                    )
                if self.trace:
                    self.trace.end(
                        f"agent_iter_{iterations}",
                        status="ok",
                        counts={"tools": 0},
                    )
                # 若已有完整 content 且跑過工具，可當 early_content；
                # 串流路徑仍建議 re-stream 以保持一致 — 有 content 時 non-stream 可用
                return {
                    "messages": messages,
                    "tools_used": tools_used,
                    "usage": usage_acc,
                    "events": events,
                    "needs_final_generation": not bool(content.strip()),
                    "early_content": content,
                }

            # --- 執行本輪工具（policy 逐一檢查）---
            if tool_resp.get("raw_message") is not None:
                messages.append(tool_resp["raw_message"])
            else:
                messages.append(
                    {
                        "role": "assistant",
                        "content": tool_resp.get("content") or "",
                        "tool_calls": tool_calls,
                    }
                )

            # 截斷單輪數量
            limited_calls = list(tool_calls)[: self.policy.max_tools()]
            # 過濾被 policy 拒絕的 call（仍需回 tool message 以免 API 報錯）
            allowed_calls = []
            denied_results = []
            for tc in limited_calls:
                name = ""
                try:
                    name = tc.function.name
                except Exception:
                    name = getattr(getattr(tc, "function", None), "name", "") or "unknown"
                dec = self.policy.may_execute(name)
                if not dec.allowed:
                    denied_results.append(
                        {
                            "name": name,
                            "display_name": name,
                            "icon": "🚫",
                            "ok": False,
                            "tool_call_id": getattr(tc, "id", "unknown"),
                            "content": f"[TOOL_DENIED] {dec.reason}",
                            "error": dec.reason,
                            "error_code": "policy_denied",
                        }
                    )
                else:
                    allowed_calls.append(tc)

            events.append(
                {
                    "type": "tool_status",
                    "status": "running",
                    "message": f"正在執行工具（第 {iterations} 輪）…",
                    "tools": [
                        {
                            "name": getattr(getattr(c, "function", None), "name", "?"),
                            "phase": "running",
                        }
                        for c in allowed_calls
                    ],
                    "step": iterations,
                    "total": max_iter,
                }
            )

            exec_results: List[Dict[str, Any]] = []
            if allowed_calls and not self.policy.shadow:
                exec_results = await self.tools.execute_calls(
                    allowed_calls,
                    context={"user_id": user_id},
                    max_calls=self.policy.max_tools(),
                )
            elif allowed_calls and self.policy.shadow:
                # Shadow：不執行，回傳 dry-run
                for c in allowed_calls:
                    name = getattr(getattr(c, "function", None), "name", "unknown")
                    exec_results.append(
                        {
                            "name": name,
                            "display_name": name,
                            "icon": "🌑",
                            "ok": True,
                            "tool_call_id": getattr(c, "id", "unknown"),
                            "content": "[SHADOW] tool not executed",
                            "error": None,
                            "error_code": None,
                        }
                    )

            all_results = denied_results + exec_results
            live = []
            for r in all_results:
                # 截斷輸出
                content = str(r.get("content") or "")
                max_out = self.policy.max_tool_output_chars()
                if len(content) > max_out:
                    content = content[:max_out] + "\n...(truncated)"
                    r = {**r, "content": content}
                tools_used.append(r)
                total_tool_calls += 1
                live.append(
                    {
                        "name": r.get("name"),
                        "display_name": r.get("display_name") or r.get("name"),
                        "icon": r.get("icon") or "🔧",
                        "ok": r.get("ok"),
                        "phase": "done" if r.get("ok") else "error",
                    }
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": r.get("tool_call_id") or "unknown",
                        "content": r.get("content") or "",
                    }
                )

            events.append(
                {
                    "type": "tool_status",
                    "status": "progress",
                    "message": f"第 {iterations} 輪工具完成",
                    "tools": live,
                    "step": iterations,
                    "total": max_iter,
                }
            )
            if self.trace:
                self.trace.end(
                    f"agent_iter_{iterations}",
                    status="ok",
                    counts={"tools": len(all_results)},
                )
            # 繼續 while：讓模型看 tool 結果再決定是否再呼叫工具

        # 超過 max_iterations
        events.append(
            {
                "type": "tool_status",
                "status": "done",
                "message": f"已達 Agent 迭代上限（{max_iter}），產生最終回答",
                "tools": [],
                "step": max_iter,
                "total": max_iter,
            }
        )
        return {
            "messages": messages,
            "tools_used": tools_used,
            "usage": usage_acc,
            "events": events,
            "needs_final_generation": True,
            "early_content": "",
            "limit_hit": "max_iterations",
        }

    async def run(
        self,
        ctx: KernelContext,
        *,
        user_id: str,
        request: Optional[KernelRequest] = None,
        stream_final: bool = False,
    ) -> Dict[str, Any]:
        """
        完整非串流：tool rounds + final complete。
        stream_final=True 時只跑 tool rounds，content 留空由呼叫端 stream。
        """
        rounds = await self.run_tool_rounds(ctx, user_id=user_id, request=request)
        messages = rounds["messages"]
        usage_acc = dict(rounds.get("usage") or {})
        tools_used = rounds.get("tools_used") or []
        events = list(rounds.get("events") or [])

        if stream_final:
            return {
                "content": rounds.get("early_content") or "",
                "messages": messages,
                "tools_used": tools_used,
                "usage": usage_acc,
                "events": events,
                "needs_final_generation": rounds.get("needs_final_generation", True)
                or not (rounds.get("early_content") or "").strip(),
            }

        content = (rounds.get("early_content") or "").strip()
        if rounds.get("needs_final_generation") or not content:
            result = await self.model.complete(
                messages,
                model=ctx.model_config_obj.model,
                temperature=ctx.strategy.temperature,
                max_tokens=ctx.strategy.max_tokens,
            )
            self._merge_usage(usage_acc, result.get("usage") or {})
            content = result.get("content") or content

        if tools_used:
            events.append(
                {
                    "type": "tool_status",
                    "status": "done",
                    "message": "工具階段完成，已產生回覆",
                    "tools": [],
                }
            )

        return {
            "content": content,
            "messages": messages,
            "tools_used": tools_used,
            "usage": usage_acc,
            "events": events,
            "needs_final_generation": False,
        }

    def _merge_usage(self, acc: dict, u: dict) -> None:
        if not u:
            return
        acc["prompt_tokens"] += int(u.get("prompt_tokens") or 0)
        acc["completion_tokens"] += int(u.get("completion_tokens") or 0)
        acc["total_tokens"] += int(
            u.get("total_tokens")
            or (
                int(u.get("prompt_tokens") or 0)
                + int(u.get("completion_tokens") or 0)
            )
        )
