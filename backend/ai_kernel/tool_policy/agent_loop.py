"""Tool Policy + Agent Loop 硬上限。"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from backend.ai_kernel.errors import AgentLoopLimitError
from backend.ai_kernel.feature_flags import KernelFlags
from backend.ai_kernel.models import KernelContext, PlanAction
from backend.ai_kernel.ports import ModelGatewayPort, ToolExecutorPort
from backend.ai_kernel.tracing import KernelTrace


class ToolPolicy:
    def __init__(self, flags: KernelFlags):
        self.flags = flags

    def max_iterations(self) -> int:
        return max(1, min(10, self.flags.max_agent_iterations))

    def max_tools(self) -> int:
        return max(1, min(10, self.flags.max_tool_calls))

    def max_tool_seconds(self) -> float:
        return max(1.0, float(self.flags.max_total_tool_seconds))


class AgentLoop:
    """
    多步 tool calling，硬上限：
    - max_iterations
    - max_tools_per_turn（每輪）
    - max_total_tool_seconds
    """

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

    async def run(
        self,
        ctx: KernelContext,
        *,
        user_id: str,
    ) -> Dict[str, Any]:
        """
        回傳:
          content, messages, tools_used, usage, events(list of tool_status dicts)
        """
        messages = list(ctx.messages)
        model = ctx.model_config_obj.model
        temperature = ctx.strategy.temperature
        max_tokens = min(1000, ctx.strategy.max_tokens)
        tools_used: List[Dict[str, Any]] = []
        events: List[Dict[str, Any]] = []
        usage_acc = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        allow = ctx.plan and ctx.plan.allow_tools
        defs = self.tools.openai_definitions() if allow else []
        if not defs:
            events.append(
                {"type": "tool_status", "status": "skipped", "message": "本次無需使用工具", "tools": []}
            )
            # direct complete
            result = await self.model.complete(
                messages,
                model=model,
                temperature=temperature,
                max_tokens=ctx.strategy.max_tokens,
            )
            u = result.get("usage") or {}
            self._merge_usage(usage_acc, u)
            return {
                "content": result.get("content") or "",
                "messages": messages,
                "tools_used": tools_used,
                "usage": usage_acc,
                "events": events,
            }

        t0 = time.perf_counter()
        iterations = 0
        max_iter = self.policy.max_iterations()

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
                raise AgentLoopLimitError("max_total_tool_seconds exceeded")

            tool_resp = await self.model.complete_with_tools(
                messages,
                tools=defs,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            self._merge_usage(usage_acc, tool_resp.get("usage") or {})

            if tool_resp.get("finish_reason") == "error":
                # 降級直接回答
                events.append(
                    {
                        "type": "tool_status",
                        "status": "error",
                        "message": "工具階段失敗，改為直接回答",
                        "tools": [],
                    }
                )
                result = await self.model.complete(
                    messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=ctx.strategy.max_tokens,
                )
                self._merge_usage(usage_acc, result.get("usage") or {})
                return {
                    "content": result.get("content") or "",
                    "messages": messages,
                    "tools_used": tools_used,
                    "usage": usage_acc,
                    "events": events,
                }

            if tool_resp.get("finish_reason") != "tool_calls" or not tool_resp.get(
                "tool_calls"
            ):
                events.append(
                    {
                        "type": "tool_status",
                        "status": "skipped",
                        "message": "本次無需使用工具",
                        "tools": [],
                    }
                )
                content = tool_resp.get("content") or ""
                if not content:
                    result = await self.model.complete(
                        messages,
                        model=model,
                        temperature=temperature,
                        max_tokens=ctx.strategy.max_tokens,
                    )
                    self._merge_usage(usage_acc, result.get("usage") or {})
                    content = result.get("content") or ""
                return {
                    "content": content,
                    "messages": messages,
                    "tools_used": tools_used,
                    "usage": usage_acc,
                    "events": events,
                }

            # execute tools
            if tool_resp.get("raw_message") is not None:
                messages.append(tool_resp["raw_message"])
            else:
                messages.append(
                    {
                        "role": "assistant",
                        "content": tool_resp.get("content") or "",
                        "tool_calls": tool_resp.get("tool_calls"),
                    }
                )

            results = await self.tools.execute_calls(
                tool_resp["tool_calls"],
                context={"user_id": user_id},
                max_calls=self.policy.max_tools(),
            )
            live = []
            for r in results:
                tools_used.append(r)
                live.append(
                    {
                        "name": r.get("name"),
                        "display_name": r.get("display_name") or r.get("name"),
                        "icon": r.get("icon") or "🔧",
                        "ok": r.get("ok"),
                        "phase": "done" if r.get("ok") is not None else "error",
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
                    "status": "done",
                    "message": "工具階段完成，正在產生回覆…",
                    "tools": live,
                    "step": len(results),
                    "total": len(results),
                }
            )

            # 下一輪用 complete 收斂
            final = await self.model.complete(
                messages,
                model=model,
                temperature=temperature,
                max_tokens=ctx.strategy.max_tokens,
            )
            self._merge_usage(usage_acc, final.get("usage") or {})
            return {
                "content": final.get("content") or "",
                "messages": messages,
                "tools_used": tools_used,
                "usage": usage_acc,
                "events": events,
            }

        raise AgentLoopLimitError(f"max_iterations={max_iter} exceeded")

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
