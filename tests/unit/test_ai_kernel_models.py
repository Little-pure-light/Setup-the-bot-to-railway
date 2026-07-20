"""P2-01: Kernel 模型與 Planner"""
import pytest

from backend.ai_kernel.models import KernelRequest, Plan, PlanAction
from backend.ai_kernel.planner import plan_request
from backend.ai_kernel.feature_flags import get_kernel_flags, KernelFlags
from backend.ai_kernel.strategies import select_response_strategy
from backend.ai_kernel.context import apply_token_budget, build_blocks, assemble_context
from backend.ai_kernel.models import ContextBlock


def test_kernel_request_defaults():
    r = KernelRequest(user_message="hi", conversation_id="c1")
    assert r.user_id == "default_user"
    assert r.stream is True


def test_plan_request_direct_chat():
    r = KernelRequest(user_message="你好呀", conversation_id="c")
    p = plan_request(r)
    assert p.action == PlanAction.DIRECT_ANSWER
    assert p.allow_tools is False


def test_plan_request_tool_hint():
    r = KernelRequest(user_message="台北天氣如何", conversation_id="c")
    p = plan_request(r, use_tools=True)
    assert p.allow_tools is True
    assert p.action == PlanAction.USE_TOOLS


def test_plan_tools_disabled():
    r = KernelRequest(user_message="搜尋新聞", conversation_id="c", use_tools=False)
    p = plan_request(r, use_tools=False)
    assert p.allow_tools is False


def test_car_mode_strategy_short_tokens():
    r = KernelRequest(user_message="hi", conversation_id="c", car_mode=True)
    cfg, st = select_response_strategy(r)
    assert st.car_mode is True
    assert st.max_tokens <= 600
    assert cfg.max_tokens == st.max_tokens


def test_voice_mode_strategy():
    r = KernelRequest(user_message="hi", conversation_id="c", voice_mode=True)
    _, st = select_response_strategy(r)
    assert st.voice_friendly is True


def test_token_budget_keeps_required_user():
    blocks = [
        ContextBlock(key="system_safety", content="S" * 100, priority=100, required=True, estimated_tokens=50),
        ContextBlock(key="memories", content="M" * 200, priority=40, required=False, estimated_tokens=100),
        ContextBlock(key="user_message", role="user", content="hello", priority=90, required=True, estimated_tokens=5),
    ]
    kept = apply_token_budget(blocks, budget=60)
    keys = {b.key for b in kept}
    assert "user_message" in keys
    assert "system_safety" in keys
    # memories too expensive
    assert "memories" not in keys


def test_flags_default_off(monkeypatch):
    monkeypatch.delenv("AI_KERNEL_ENABLED", raising=False)
    f = get_kernel_flags()
    assert f.enabled is False
