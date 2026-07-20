"""Feature flags for AI Kernel migration (Strangler)."""
from __future__ import annotations

import os
from dataclasses import dataclass


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class KernelFlags:
    enabled: bool = False
    shadow_mode: bool = False
    debug_enabled: bool = False
    max_agent_iterations: int = 3
    max_tool_calls: int = 5
    max_total_tool_seconds: float = 30.0
    max_tool_output_chars: int = 12000
    context_token_budget: int = 12000
    fallback_to_legacy_on_fatal: bool = True


def get_kernel_flags() -> KernelFlags:
    return KernelFlags(
        enabled=_bool_env("AI_KERNEL_ENABLED", False),
        shadow_mode=_bool_env("AI_KERNEL_SHADOW_MODE", False),
        debug_enabled=_bool_env("KERNEL_DEBUG_ENABLED", False),
        max_agent_iterations=_int_env("KERNEL_MAX_AGENT_ITERATIONS", 3),
        max_tool_calls=_int_env("KERNEL_MAX_TOOL_CALLS", 5),
        max_total_tool_seconds=float(
            os.getenv("KERNEL_MAX_TOTAL_TOOL_SECONDS", "30") or 30
        ),
        max_tool_output_chars=_int_env("KERNEL_MAX_TOOL_OUTPUT_CHARS", 12000),
        context_token_budget=_int_env("KERNEL_CONTEXT_TOKEN_BUDGET", 12000),
        fallback_to_legacy_on_fatal=_bool_env(
            "KERNEL_FALLBACK_TO_LEGACY", True
        ),
    )
