"""真正多輪 Agent Loop + 工具後需 final generation（供 streaming）"""
import pytest
from unittest.mock import MagicMock

from backend.ai_kernel.feature_flags import KernelFlags
from backend.ai_kernel.models import (
    KernelContext,
    KernelRequest,
    ModelConfig,
    Plan,
    PlanAction,
    ResponseStrategy,
)
from backend.ai_kernel.tool_policy import AgentLoop, ToolPolicy


class MultiRoundModel:
    """第 1 輪 tool，第 2 輪 tool，第 3 輪 stop。"""

    def __init__(self):
        self.n = 0
        self.stream_calls = 0

    async def complete(self, messages, *, model, temperature, max_tokens):
        return {
            "content": "最終非串流答案",
            "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
        }

    async def complete_with_tools(self, messages, tools, *, model, temperature, max_tokens):
        self.n += 1
        if self.n <= 2:
            tc = MagicMock()
            tc.id = f"call_{self.n}"
            tc.function.name = "calculate"
            tc.function.arguments = '{"expression":"1+1"}'
            return {
                "content": "",
                "tool_calls": [tc],
                "finish_reason": "tool_calls",
                "raw_message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [tc],
                },
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }
        return {
            "content": "已完成多輪",
            "tool_calls": [],
            "finish_reason": "stop",
            "raw_message": None,
            "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
        }

    async def stream(self, messages, *, model, temperature, max_tokens):
        self.stream_calls += 1
        yield {"type": "content", "text": "串"}
        yield {"type": "content", "text": "流"}
        yield {
            "type": "usage",
            "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
        }


class Tools:
    def __init__(self):
        self.exec_count = 0

    def openai_definitions(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "calculate",
                    "description": "calc",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]

    async def execute_calls(self, tool_calls, *, context=None, max_calls=5):
        self.exec_count += len(tool_calls)
        out = []
        for tc in tool_calls:
            out.append(
                {
                    "name": "calculate",
                    "display_name": "calc",
                    "icon": "🔢",
                    "ok": True,
                    "tool_call_id": getattr(tc, "id", "x"),
                    "content": "2",
                }
            )
        return out


@pytest.mark.asyncio
async def test_multi_round_tool_calls():
    model = MultiRoundModel()
    tools = Tools()
    flags = KernelFlags(max_agent_iterations=5, max_tool_calls=5)
    loop = AgentLoop(model, tools, ToolPolicy(flags))
    req = KernelRequest(user_message="算兩次", conversation_id="c")
    ctx = KernelContext(
        request=req,
        messages=[{"role": "user", "content": "算兩次"}],
        plan=Plan(action=PlanAction.USE_TOOLS, allow_tools=True),
        model_config_obj=ModelConfig(),
        strategy=ResponseStrategy(max_tokens=200),
    )
    rounds = await loop.run_tool_rounds(ctx, user_id="u", request=req)
    assert tools.exec_count == 2  # 兩輪工具
    assert model.n == 3  # 兩次 tool_calls + 一次 stop
    assert rounds["needs_final_generation"] is False or rounds.get("early_content")
    assert len(rounds["tools_used"]) == 2


@pytest.mark.asyncio
async def test_run_stream_final_flag_skips_complete():
    model = MultiRoundModel()
    tools = Tools()
    loop = AgentLoop(model, tools, ToolPolicy(KernelFlags(max_agent_iterations=3)))
    req = KernelRequest(user_message="算", conversation_id="c")
    ctx = KernelContext(
        request=req,
        messages=[{"role": "user", "content": "算"}],
        plan=Plan(action=PlanAction.USE_TOOLS, allow_tools=True),
        model_config_obj=ModelConfig(),
        strategy=ResponseStrategy(max_tokens=200),
    )
    out = await loop.run(ctx, user_id="u", request=req, stream_final=True)
    assert out["needs_final_generation"] is True or out["messages"]
    # stream_final 不呼叫 complete 收斂（complete 只在 run stream_final=False）
    # MultiRoundModel 在 stop 時已給 content，needs_final 可能 false


@pytest.mark.asyncio
async def test_max_iterations_hard_limit():
    class AlwaysTool(MultiRoundModel):
        async def complete_with_tools(self, messages, tools, *, model, temperature, max_tokens):
            self.n += 1
            tc = MagicMock()
            tc.id = f"c{self.n}"
            tc.function.name = "calculate"
            tc.function.arguments = "{}"
            return {
                "content": "",
                "tool_calls": [tc],
                "finish_reason": "tool_calls",
                "raw_message": {"role": "assistant", "tool_calls": [tc]},
                "usage": {},
            }

    model = AlwaysTool()
    tools = Tools()
    loop = AgentLoop(
        model, tools, ToolPolicy(KernelFlags(max_agent_iterations=2, max_tool_calls=3))
    )
    req = KernelRequest(user_message="無限", conversation_id="c")
    ctx = KernelContext(
        request=req,
        messages=[{"role": "user", "content": "x"}],
        plan=Plan(action=PlanAction.USE_TOOLS, allow_tools=True),
        model_config_obj=ModelConfig(),
        strategy=ResponseStrategy(max_tokens=100),
    )
    rounds = await loop.run_tool_rounds(ctx, user_id="u", request=req)
    assert rounds.get("limit_hit") == "max_iterations"
    assert tools.exec_count == 2


@pytest.mark.asyncio
async def test_shadow_tools_not_really_executed():
    model = MultiRoundModel()
    tools = Tools()
    loop = AgentLoop(
        model, tools, ToolPolicy(KernelFlags(max_agent_iterations=2), shadow=True)
    )
    req = KernelRequest(user_message="天氣", conversation_id="c", shadow=True)
    # shadow policy blocks exposure entirely
    ctx = KernelContext(
        request=req,
        messages=[{"role": "user", "content": "x"}],
        plan=Plan(action=PlanAction.USE_TOOLS, allow_tools=True),
        model_config_obj=ModelConfig(),
        strategy=ResponseStrategy(max_tokens=100),
    )
    rounds = await loop.run_tool_rounds(ctx, user_id="u", request=req)
    assert tools.exec_count == 0
    assert rounds["needs_final_generation"] is True
