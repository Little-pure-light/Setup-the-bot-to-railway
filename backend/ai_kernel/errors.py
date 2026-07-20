"""Kernel 統一錯誤類型（不依賴 SDK）。"""
from __future__ import annotations


class KernelError(Exception):
    """Base kernel error."""

    code: str = "KERNEL_ERROR"

    def __init__(self, message: str = "", *, code: str | None = None):
        super().__init__(message)
        if code:
            self.code = code
        self.message = message or str(self)


class KernelFatalError(KernelError):
    """應回退 Legacy 的致命錯誤。"""

    code = "KERNEL_FATAL"


class ModelGatewayError(KernelError):
    code = "MODEL_GATEWAY_ERROR"


class ModelTimeoutError(ModelGatewayError):
    code = "MODEL_TIMEOUT"


class PlannerError(KernelError):
    code = "PLANNER_ERROR"


class ContextBuildError(KernelError):
    code = "CONTEXT_BUILD_ERROR"


class ToolPolicyError(KernelError):
    code = "TOOL_POLICY_ERROR"


class BudgetExceededError(KernelError):
    code = "BUDGET_EXCEEDED"


class ModerationBlockedError(KernelError):
    code = "MODERATION_BLOCKED"


class AgentLoopLimitError(KernelError):
    code = "AGENT_LOOP_LIMIT"
