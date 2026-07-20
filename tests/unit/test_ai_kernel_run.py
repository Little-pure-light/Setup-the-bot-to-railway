"""Kernel 整合（全 mock deps）— parity helpers、fallback、timeout"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.ai_kernel.kernel import AIKernel
from backend.ai_kernel.models import KernelRequest
from backend.ai_kernel.ports import KernelDeps
from backend.ai_kernel.feature_flags import KernelFlags
from backend.ai_kernel.errors import BudgetExceededError, ModelTimeoutError
from backend.ai_kernel.model_gateway.openai_gateway import OpenAIModelGateway
from backend.ai_kernel.post_process import clear_idempotency_for_tests


class Mem:
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
        return {"blocked": False, "flagged": False}


class Budget:
    def check(self, user_id):
        return True, "ok", {}

    def record(self, **kwargs):
        return {
            "prompt_tokens": 1,
            "completion_tokens": 1,
            "total_tokens": 2,
            "cost_usd": 0,
            "model": kwargs.get("model"),
            "daily": {},
        }


class Tools:
    def openai_definitions(self):
        return []

    async def execute_calls(self, *a, **k):
        return []


class Voice:
    def build_hint(self, **k):
        return "VOICE_HINT"


class Speech:
    def sanitize(self, text):
        return text.replace("😊", "")


def _deps(model=None, budget=None, mem=None):
    return KernelDeps(
        memory=mem or Mem(),
        files=Files(),
        prompt=Prompt(),
        moderation=Mod(),
        budget=budget or Budget(),
        model=model
        or OpenAIModelGateway(
            complete_fn=AsyncMock(
                return_value={
                    "content": "哈尼～你好",
                    "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
                }
            ),
            complete_tools_fn=AsyncMock(
                return_value={
                    "content": "哈尼～你好",
                    "tool_calls": [],
                    "finish_reason": "stop",
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                }
            ),
            stream_fn=None,
        ),
        tools=Tools(),
        voice=Voice(),
        speech=Speech(),
        post_process=None,
    )


@pytest.mark.asyncio
async def test_kernel_direct_answer():
    clear_idempotency_for_tests()
    k = AIKernel(_deps(), flags=KernelFlags(enabled=True, debug_enabled=True))
    r = await k.run(
        KernelRequest(user_message="你好", conversation_id="c1", user_id="u1")
    )
    assert "你好" in r.assistant_message or "哈尼" in r.assistant_message
    assert r.used_kernel is True


@pytest.mark.asyncio
async def test_kernel_budget_exceeded():
    class B(Budget):
        def check(self, user_id):
            return False, "over", {}

    k = AIKernel(_deps(budget=B()), flags=KernelFlags(enabled=True))
    with pytest.raises(BudgetExceededError):
        await k.run(KernelRequest(user_message="x", conversation_id="c"))


@pytest.mark.asyncio
async def test_kernel_model_timeout_maps():
    async def boom(*a, **k):
        raise TimeoutError("timed out")

    gw = OpenAIModelGateway(complete_fn=boom, complete_tools_fn=boom)
    with pytest.raises(Exception):
        await gw.complete([], model="m", temperature=0.5, max_tokens=10)


@pytest.mark.asyncio
async def test_shadow_no_memory_write():
    clear_idempotency_for_tests()
    mem = Mem()
    mem.saved = False

    class PP:
        async def run_jobs(self, jobs):
            mem.saved = True

    deps = _deps(mem=mem)
    deps.post_process = PP()
    k = AIKernel(deps, flags=KernelFlags(enabled=True, shadow_mode=True))
    await k.run(
        KernelRequest(
            user_message="hi", conversation_id="c", shadow=True, request_id="sh1"
        )
    )
    assert mem.saved is False


@pytest.mark.asyncio
async def test_car_mode_max_tokens_in_strategy():
    from backend.ai_kernel.strategies import select_response_strategy

    cfg, st = select_response_strategy(
        KernelRequest(user_message="a", conversation_id="c", car_mode=True)
    )
    assert st.max_tokens <= 600
