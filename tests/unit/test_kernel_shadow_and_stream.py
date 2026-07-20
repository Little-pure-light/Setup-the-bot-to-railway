"""Shadow 無副作用 + 工具後串流最終答案"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.ai_kernel.feature_flags import KernelFlags
from backend.ai_kernel.kernel import AIKernel
from backend.ai_kernel.models import KernelRequest
from backend.ai_kernel.ports import KernelDeps
from backend.ai_kernel.model_gateway.openai_gateway import OpenAIModelGateway
from backend.ai_kernel.post_process import clear_idempotency_for_tests


class Mem:
    def __init__(self):
        self.saved = False

    async def recall(self, *a, **k):
        return ""

    def history(self, *a, **k):
        return ""

    async def save(self, *a, **k):
        self.saved = True


class Files:
    def get_file_content(self, cid):
        return ""


class Prompt:
    async def build(self, user_message, recalled_memories, conversation_history, file_content):
        return (
            [
                {"role": "system", "content": "sys"},
                {"role": "user", "content": user_message},
            ],
            {"dominant_emotion": "neutral", "intensity": 0.5, "confidence": 0.5, "emotions": {}},
        )


class Mod:
    async def check(self, text):
        return {"blocked": False}


class Budget:
    def __init__(self):
        self.records = 0

    def check(self, user_id):
        return True, "ok", {}

    def record(self, **kwargs):
        self.records += 1
        return {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2, "cost_usd": 0, "model": "m", "daily": {}}


class Tools:
    def __init__(self):
        self.execs = 0

    def openai_definitions(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "calculate",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]

    async def execute_calls(self, tool_calls, *, context=None, max_calls=5):
        self.execs += 1
        return [
            {
                "name": "calculate",
                "ok": True,
                "tool_call_id": "1",
                "content": "2",
                "display_name": "calc",
                "icon": "🔢",
            }
        ]


class Voice:
    def build_hint(self, **k):
        return ""


class Speech:
    def sanitize(self, text):
        return text


class StreamModel:
    def __init__(self):
        self.streamed = []
        self.n = 0

    async def complete(self, messages, *, model, temperature, max_tokens):
        return {
            "content": "nonstream",
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

    async def complete_with_tools(self, messages, tools, *, model, temperature, max_tokens):
        self.n += 1
        if self.n == 1 and tools:
            tc = MagicMock()
            tc.id = "t1"
            tc.function.name = "calculate"
            tc.function.arguments = "{}"
            return {
                "content": "",
                "tool_calls": [tc],
                "finish_reason": "tool_calls",
                "raw_message": {"role": "assistant", "tool_calls": [tc]},
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }
        return {
            "content": "done",
            "tool_calls": [],
            "finish_reason": "stop",
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

    async def stream(self, messages, *, model, temperature, max_tokens):
        for t in ["工", "具", "後", "串", "流"]:
            self.streamed.append(t)
            yield {"type": "content", "text": t}
        yield {
            "type": "usage",
            "usage": {"prompt_tokens": 1, "completion_tokens": 5, "total_tokens": 6},
        }


def _deps(mem=None, budget=None, tools=None, model=None):
    m = model or StreamModel()
    return KernelDeps(
        memory=mem or Mem(),
        files=Files(),
        prompt=Prompt(),
        moderation=Mod(),
        budget=budget or Budget(),
        model=OpenAIModelGateway(
            complete_fn=m.complete,
            complete_tools_fn=m.complete_with_tools,
            stream_fn=m.stream,
        ),
        tools=tools or Tools(),
        voice=Voice(),
        speech=Speech(),
        post_process=None,
    ), m


@pytest.mark.asyncio
async def test_shadow_no_budget_record_no_tools_no_memory():
    clear_idempotency_for_tests()
    mem = Mem()
    budget = Budget()
    tools = Tools()
    deps, _ = _deps(mem=mem, budget=budget, tools=tools)

    class PP:
        async def run_jobs(self, jobs):
            mem.saved = True

    deps.post_process = PP()
    k = AIKernel(deps, flags=KernelFlags(enabled=True, shadow_mode=True))
    await k.run(
        KernelRequest(
            user_message="算 1+1",
            conversation_id="c",
            shadow=True,
            use_tools=True,
            request_id="sh1",
        )
    )
    assert budget.records == 0
    assert tools.execs == 0
    assert mem.saved is False


@pytest.mark.asyncio
async def test_stream_after_tools_uses_token_stream():
    clear_idempotency_for_tests()
    deps, model = _deps()
    k = AIKernel(deps, flags=KernelFlags(enabled=True, max_agent_iterations=3))
    chunks = []
    async for ev in k.run_stream(
        KernelRequest(
            user_message="計算 1+1",
            conversation_id="c",
            use_tools=True,
            request_id="s1",
        )
    ):
        if ev.type == "content":
            chunks.append(ev.text)
    assert model.streamed  # 最終答案走 stream
    assert "".join(chunks) == "工具後串流"
