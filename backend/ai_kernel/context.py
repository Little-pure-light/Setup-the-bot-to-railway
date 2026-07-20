"""Context Builder — 模組化 ContextBlock + Token Budget。"""
from __future__ import annotations

from typing import List

from backend.ai_kernel.models import ContextBlock, KernelContext, KernelRequest


def _est_tokens(text: str) -> int:
    # 粗估：中英混合約 2 字元/token
    if not text:
        return 0
    return max(1, len(text) // 2)


def build_blocks(
    request: KernelRequest,
    *,
    system_prompt: str,
    recalled_memories: str,
    conversation_history: str,
    file_content: str,
    voice_hint: str = "",
) -> List[ContextBlock]:
    blocks: List[ContextBlock] = []

    # 最高優先：安全與人格 system
    sys = system_prompt or ""
    if voice_hint:
        sys = f"{sys}\n\n{voice_hint}" if sys else voice_hint
    blocks.append(
        ContextBlock(
            key="system_safety",
            role="system",
            content=sys,
            priority=100,
            estimated_tokens=_est_tokens(sys),
            required=True,
        )
    )

    if recalled_memories:
        # 去重：簡單正規化
        mem = _dedupe_lines(recalled_memories)
        blocks.append(
            ContextBlock(
                key="memories",
                role="system",
                content=f"### 記憶與上下文\n{mem}",
                priority=40,
                estimated_tokens=_est_tokens(mem),
                required=False,
            )
        )

    if conversation_history:
        hist = conversation_history
        # 限制長度
        if len(hist) > 4000:
            hist = hist[-4000:]
        blocks.append(
            ContextBlock(
                key="history",
                role="system",
                content=f"### 最近對話歷史\n{hist}",
                priority=30,
                estimated_tokens=_est_tokens(hist),
                required=False,
            )
        )

    if file_content:
        fc = file_content[:3000]
        blocks.append(
            ContextBlock(
                key="file",
                role="system",
                content=f"### 附件/視覺\n{fc}",
                priority=50,
                estimated_tokens=_est_tokens(fc),
                required=False,
            )
        )

    # 使用者訊息不可被裁掉
    blocks.append(
        ContextBlock(
            key="user_message",
            role="user",
            content=request.user_message,
            priority=90,
            estimated_tokens=_est_tokens(request.user_message),
            required=True,
        )
    )
    return blocks


def apply_token_budget(
    blocks: List[ContextBlock], budget: int
) -> List[ContextBlock]:
    """保留 required；其餘依 priority 高到低放入，直到預算用盡。"""
    required = [b for b in blocks if b.required]
    optional = sorted(
        [b for b in blocks if not b.required],
        key=lambda b: b.priority,
        reverse=True,
    )
    used = sum(b.estimated_tokens for b in required)
    kept = list(required)
    for b in optional:
        if used + b.estimated_tokens <= budget:
            kept.append(b)
            used += b.estimated_tokens
    # 維持大致順序：system 類先、user 最後
    kept.sort(key=lambda b: (0 if b.role != "user" else 1, -b.priority))
    return kept


def blocks_to_messages(blocks: List[ContextBlock]) -> list:
    """合併同 role 的 system 區塊為單一 system message。"""
    system_parts = [b.content for b in blocks if b.role == "system" and b.content]
    user_parts = [b.content for b in blocks if b.role == "user" and b.content]
    messages = []
    if system_parts:
        messages.append({"role": "system", "content": "\n\n".join(system_parts)})
    for u in user_parts:
        messages.append({"role": "user", "content": u})
    return messages


def _dedupe_lines(text: str) -> str:
    seen = set()
    out = []
    for line in text.splitlines():
        key = line.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(line)
    return "\n".join(out)


def assemble_context(
    request: KernelRequest,
    *,
    system_prompt: str,
    recalled_memories: str,
    conversation_history: str,
    file_content: str,
    voice_hint: str,
    emotion_analysis: dict,
    token_budget: int,
) -> KernelContext:
    blocks = build_blocks(
        request,
        system_prompt=system_prompt,
        recalled_memories=recalled_memories,
        conversation_history=conversation_history,
        file_content=file_content,
        voice_hint=voice_hint,
    )
    blocks = apply_token_budget(blocks, token_budget)
    messages = blocks_to_messages(blocks)
    return KernelContext(
        request=request,
        blocks=blocks,
        messages=messages,
        emotion_analysis=emotion_analysis or {},
        recalled_memories=recalled_memories or "",
        conversation_history=conversation_history or "",
        file_content=file_content or "",
    )
