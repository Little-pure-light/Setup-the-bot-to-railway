"""
實際 Tool Policy：allowlist / blocklist / risk / 模式限制。

不執行工具；只決定「能否暴露給模型」與「能否執行」。
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from backend.ai_kernel.feature_flags import KernelFlags
from backend.ai_kernel.models import KernelRequest


# 與 registry 對齊的預設封鎖名
DEFAULT_BLOCKED: Set[str] = {
    "shell",
    "bash",
    "cmd",
    "powershell",
    "exec",
    "eval",
    "python",
    "run_code",
    "code_interpreter",
    "file_write",
    "write_file",
    "delete_file",
    "rm",
    "http_request",
    "fetch_url_raw",
    "subprocess",
    "os_system",
    "sql",
    "database",
}

# 車載 / 語音預設允許的低風險工具
VOICE_SAFE_TOOLS: Set[str] = {
    "get_current_time",
    "calculate",
    "convert_units",
    "get_weather",
}


@dataclass
class ToolPolicyDecision:
    allowed: bool
    reason: str = "ok"
    filtered_definitions: List[Dict[str, Any]] = field(default_factory=list)


class ToolPolicy:
    """
    工具政策引擎。

    - max_iterations / max_tools / max_tool_seconds：硬上限
    - blocked_names：永不執行
    - allowlist（可選環境變數 KERNEL_TOOL_ALLOWLIST=a,b,c）
    - car/voice：僅 voice-safe 工具（可關閉 KERNEL_VOICE_TOOL_RESTRICT=false）
    - shadow：禁止執行任何工具（dry-run）
    """

    def __init__(self, flags: KernelFlags, *, shadow: bool = False):
        self.flags = flags
        self.shadow = shadow
        self.blocked = set(DEFAULT_BLOCKED)
        extra_block = os.getenv("KERNEL_TOOL_BLOCKLIST", "")
        if extra_block.strip():
            self.blocked |= {x.strip() for x in extra_block.split(",") if x.strip()}
        allow_raw = os.getenv("KERNEL_TOOL_ALLOWLIST", "").strip()
        self.allowlist: Optional[Set[str]] = None
        if allow_raw:
            self.allowlist = {x.strip() for x in allow_raw.split(",") if x.strip()}
        self.voice_restrict = os.getenv("KERNEL_VOICE_TOOL_RESTRICT", "true").lower() not in (
            "0",
            "false",
            "no",
        )

    def max_iterations(self) -> int:
        return max(1, min(10, self.flags.max_agent_iterations))

    def max_tools(self) -> int:
        return max(1, min(10, self.flags.max_tool_calls))

    def max_tool_seconds(self) -> float:
        return max(1.0, float(self.flags.max_total_tool_seconds))

    def max_tool_output_chars(self) -> int:
        return max(500, int(self.flags.max_tool_output_chars))

    def is_name_blocked(self, name: str) -> bool:
        if not isinstance(name, str):
            return True
        n = name.strip().lower()
        if not n:
            return True
        if n in self.blocked:
            return True
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", n):
            return True
        return False

    def filter_definitions(
        self,
        definitions: List[Dict[str, Any]],
        request: Optional[KernelRequest] = None,
    ) -> List[Dict[str, Any]]:
        """過濾給模型看的 tools 陣列。"""
        out: List[Dict[str, Any]] = []
        for d in definitions or []:
            fn = (d.get("function") or {}) if isinstance(d, dict) else {}
            name = (fn.get("name") or "").strip()
            if self.is_name_blocked(name):
                continue
            if self.allowlist is not None and name not in self.allowlist:
                continue
            if request and self.voice_restrict and (request.car_mode or request.voice_mode):
                if name not in VOICE_SAFE_TOOLS:
                    continue
            # high risk 通常 registry 已排除；雙保險
            out.append(d)
        return out

    def may_execute(self, name: str) -> ToolPolicyDecision:
        if self.shadow:
            return ToolPolicyDecision(False, "shadow_mode_no_tools")
        if self.is_name_blocked(name):
            return ToolPolicyDecision(False, f"blocked:{name}")
        if self.allowlist is not None and name not in self.allowlist:
            return ToolPolicyDecision(False, f"not_in_allowlist:{name}")
        return ToolPolicyDecision(True, "ok")

    def decide_exposure(
        self,
        definitions: List[Dict[str, Any]],
        request: Optional[KernelRequest] = None,
        *,
        allow_tools: bool = True,
    ) -> ToolPolicyDecision:
        if self.shadow:
            return ToolPolicyDecision(False, "shadow_mode", [])
        if not allow_tools:
            return ToolPolicyDecision(False, "tools_disabled", [])
        filtered = self.filter_definitions(definitions, request)
        if not filtered:
            return ToolPolicyDecision(False, "no_tools_after_filter", [])
        return ToolPolicyDecision(True, "ok", filtered)
