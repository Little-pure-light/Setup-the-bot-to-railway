"""Tool Policy 實際規則測試"""
from backend.ai_kernel.feature_flags import KernelFlags
from backend.ai_kernel.models import KernelRequest
from backend.ai_kernel.tool_policy import ToolPolicy, VOICE_SAFE_TOOLS


def _defs(*names):
    return [
        {"type": "function", "function": {"name": n, "description": n, "parameters": {}}}
        for n in names
    ]


def test_blocked_shell_never_exposed():
    p = ToolPolicy(KernelFlags())
    d = p.filter_definitions(_defs("calculate", "shell", "bash"))
    names = [x["function"]["name"] for x in d]
    assert "calculate" in names
    assert "shell" not in names
    assert "bash" not in names


def test_allowlist_restricts(monkeypatch):
    monkeypatch.setenv("KERNEL_TOOL_ALLOWLIST", "calculate,get_current_time")
    p = ToolPolicy(KernelFlags())
    d = p.filter_definitions(_defs("calculate", "web_search", "get_weather"))
    names = [x["function"]["name"] for x in d]
    assert names == ["calculate"]


def test_voice_mode_only_safe_tools():
    p = ToolPolicy(KernelFlags())
    req = KernelRequest(user_message="x", conversation_id="c", voice_mode=True)
    d = p.filter_definitions(
        _defs("web_search", "get_current_time", "calculate"), req
    )
    names = set(x["function"]["name"] for x in d)
    assert "web_search" not in names
    assert names <= VOICE_SAFE_TOOLS


def test_shadow_may_not_execute():
    p = ToolPolicy(KernelFlags(), shadow=True)
    dec = p.may_execute("calculate")
    assert dec.allowed is False
    assert "shadow" in dec.reason


def test_shadow_decide_exposure_empty():
    p = ToolPolicy(KernelFlags(), shadow=True)
    dec = p.decide_exposure(_defs("calculate"), allow_tools=True)
    assert dec.allowed is False
    assert dec.filtered_definitions == []
