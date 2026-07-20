"""Post-Processing Pipeline — 冪等、可跳過副作用。"""
from __future__ import annotations

import logging
from typing import Dict, Set

from backend.ai_kernel.models import KernelResult, PostProcessJob

logger = logging.getLogger("ai_kernel.post_process")

# request_id + operation 防重
_DONE: Set[str] = set()


def _key(job: PostProcessJob) -> str:
    return f"{job.request_id}:{job.operation}:{job.conversation_id}"


def should_skip_memory_write(assistant_message: str) -> bool:
    text = (assistant_message or "").strip()
    if not text:
        return True
    if text.startswith("[ERROR]"):
        return True
    if "（串流已中斷）" in text:
        return True
    return False


def build_post_process_jobs(
    result: KernelResult,
    *,
    request_id: str,
    user_id: str,
    user_message: str,
    ai_id: str,
    shadow: bool,
) -> list[PostProcessJob]:
    if shadow or result.blocked or should_skip_memory_write(result.assistant_message):
        return []
    return [
        PostProcessJob(
            request_id=request_id or result.trace_id or "no-rid",
            operation="save_memory",
            conversation_id=result.conversation_id,
            user_id=user_id,
            user_message=user_message,
            assistant_message=result.assistant_message,
            emotion_analysis=result.emotion_analysis,
            ai_id=ai_id,
            skip_side_effects=shadow,
        )
    ]


async def run_post_process(
    jobs: list[PostProcessJob],
    *,
    memory_save_fn,
    shadow: bool = False,
) -> Dict[str, int]:
    """
    memory_save_fn(job) -> awaitable
    回傳 stats。
    """
    ran = 0
    skipped = 0
    for job in jobs:
        k = _key(job)
        if k in _DONE:
            skipped += 1
            continue
        if shadow or job.skip_side_effects:
            skipped += 1
            continue
        if job.operation == "save_memory":
            if should_skip_memory_write(job.assistant_message):
                skipped += 1
                continue
            try:
                await memory_save_fn(job)
                _DONE.add(k)
                ran += 1
            except Exception as e:
                logger.warning("post_process save_memory failed: %s", type(e).__name__)
        else:
            skipped += 1
    # 防止集合無限增長
    if len(_DONE) > 5000:
        for item in list(_DONE)[:2000]:
            _DONE.discard(item)
    return {"ran": ran, "skipped": skipped}


def clear_idempotency_for_tests() -> None:
    _DONE.clear()
