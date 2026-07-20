"""
AI Kernel — 可替換、可測試的對話核心。

預設關閉：AI_KERNEL_ENABLED=false → 使用 Legacy chat_router 流程。
"""
from backend.ai_kernel.feature_flags import KernelFlags, get_kernel_flags
from backend.ai_kernel.kernel import AIKernel, run_kernel_chat
from backend.ai_kernel.models import KernelRequest, KernelResult

__all__ = [
    "AIKernel",
    "KernelRequest",
    "KernelResult",
    "KernelFlags",
    "get_kernel_flags",
    "run_kernel_chat",
]
