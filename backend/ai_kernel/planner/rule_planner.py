"""RulePlanner — 一般聊天不增加額外 LLM 呼叫。"""
from __future__ import annotations

import re
from typing import Optional

from pydantic import ValidationError

from backend.ai_kernel.models import KernelRequest, Plan, PlanAction, PlanStep


# 觸發工具的簡易規則（中英）
_TOOL_HINTS = re.compile(
    r"(搜尋|查一下|天氣|幾點|現在時間|計算|算一下|換算|提醒|新聞|latest|search|weather|calculate|convert)",
    re.I,
)


class RulePlanner:
    """規則規劃器：不呼叫 LLM。"""

    def plan(self, request: KernelRequest, *, use_tools: bool = True) -> Plan:
        try:
            if not use_tools or not request.use_tools:
                return Plan(
                    action=PlanAction.DIRECT_ANSWER,
                    allow_tools=False,
                    reason="tools_disabled",
                    steps=[PlanStep(action="answer", rationale="no tools")],
                )
            if request.car_mode or request.voice_mode:
                # 車載/語音：仍可工具，但標記 short
                if _TOOL_HINTS.search(request.user_message or ""):
                    return Plan(
                        action=PlanAction.USE_TOOLS,
                        allow_tools=True,
                        reason="voice_or_car_with_tool_hint",
                        steps=[
                            PlanStep(action="tool", rationale="hint matched"),
                            PlanStep(action="answer", rationale="summarize short"),
                        ],
                    )
                return Plan(
                    action=PlanAction.SHORT_VOICE,
                    allow_tools=False,
                    reason="voice_direct",
                    steps=[PlanStep(action="answer", rationale="short voice reply")],
                )
            if _TOOL_HINTS.search(request.user_message or ""):
                return Plan(
                    action=PlanAction.USE_TOOLS,
                    allow_tools=True,
                    reason="rule_tool_hint",
                    steps=[PlanStep(action="tool", rationale="keyword")],
                )
            return Plan(
                action=PlanAction.DIRECT_ANSWER,
                allow_tools=False,
                reason="default_chat",
                steps=[PlanStep(action="answer", rationale="direct")],
            )
        except Exception:
            return _fallback_plan()


def _fallback_plan() -> Plan:
    return Plan(
        action=PlanAction.DIRECT_ANSWER,
        allow_tools=False,
        reason="planner_fallback",
        steps=[PlanStep(action="answer", rationale="fallback")],
    )


def plan_request(request: KernelRequest, *, use_tools: bool = True) -> Plan:
    """驗證後回傳 Plan；驗證失敗 → direct_answer。"""
    raw = RulePlanner().plan(request, use_tools=use_tools)
    try:
        return Plan.model_validate(raw.model_dump())
    except ValidationError:
        return _fallback_plan()
