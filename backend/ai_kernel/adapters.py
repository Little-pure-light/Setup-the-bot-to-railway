"""
Adapters — 將現有 backend/modules 接到 Kernel Ports。
此檔可 import 既有服務；Kernel 核心不 import 此檔內的全域。
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from backend.ai_kernel.models import PostProcessJob
from backend.ai_kernel.ports import KernelDeps
from backend.ai_kernel.post_process import run_post_process

logger = logging.getLogger("ai_kernel.adapters")


class MemoryAdapter:
    def __init__(self, memory_system):
        self.ms = memory_system

    async def recall(self, user_message: str, conversation_id: str, user_id: str) -> str:
        try:
            return await self.ms.recall_memories(
                user_message, conversation_id, user_id=user_id
            )
        except Exception as e:
            logger.warning("memory recall failed: %s", type(e).__name__)
            return ""

    def history(self, conversation_id: str, limit: int = 5) -> str:
        try:
            return self.ms.get_conversation_history(conversation_id, limit=limit) or ""
        except Exception as e:
            logger.warning("memory history failed: %s", type(e).__name__)
            return ""

    async def save(
        self,
        conversation_id: str,
        user_input: str,
        bot_response: str,
        emotion_analysis: dict,
        *,
        ai_id: str,
        user_id: Optional[str],
    ) -> None:
        await self.ms.save_memory(
            conversation_id,
            user_input,
            bot_response,
            emotion_analysis,
            ai_id=ai_id,
            user_id=user_id,
        )


class FileContextAdapter:
    def __init__(self, redis_interface):
        self.redis = redis_interface

    def get_file_content(self, conversation_id: str) -> str:
        try:
            if not self.redis or not getattr(self.redis, "redis", None):
                return ""
            keys = self.redis.redis.keys(f"upload:{conversation_id}:*")
            if not keys:
                return ""
            latest_key = keys[-1]
            file_data_json = self.redis.redis.get(latest_key)
            if not file_data_json:
                return ""
            file_data = json.loads(file_data_json)
            file_content = (
                file_data.get("vision_analysis") or file_data.get("content") or ""
            )
            if file_data.get("is_image"):
                fname = file_data.get("file_name") or "image"
                file_content = f"【使用者上傳圖片：{fname}】\n視覺分析：\n{file_content}"
            return file_content
        except Exception as e:
            logger.warning("file context failed: %s", type(e).__name__)
            return ""


class PromptAdapter:
    def __init__(self, prompt_engine):
        self.pe = prompt_engine

    async def build(
        self,
        user_message: str,
        recalled_memories: str,
        conversation_history: str,
        file_content: str,
    ):
        return await self.pe.build_prompt(
            user_message,
            recalled_memories,
            conversation_history,
            file_content,
        )


class ModerationAdapter:
    def __init__(self, client=None):
        self.client = client

    async def check(self, text: str) -> dict:
        from backend.moderation import moderate_text

        return await moderate_text(text, client=self.client)


class BudgetAdapter:
    def __init__(self, tracker):
        self.tracker = tracker

    def check(self, user_id: str):
        return self.tracker.check_budget(user_id)

    def record(
        self,
        *,
        user_id: str,
        conversation_id: str,
        model: str,
        usage: dict,
        endpoint: str,
        meta: Optional[dict] = None,
    ) -> dict:
        u = usage or {}
        row = self.tracker.record(
            user_id=user_id,
            conversation_id=conversation_id,
            model=model,
            prompt_tokens=int(u.get("prompt_tokens") or 0),
            completion_tokens=int(u.get("completion_tokens") or 0),
            total_tokens=int(u.get("total_tokens") or 0) or None,
            endpoint=endpoint,
            meta=meta,
        )
        summary = self.tracker.get_user_daily_summary(user_id)
        return {
            "prompt_tokens": row["prompt_tokens"],
            "completion_tokens": row["completion_tokens"],
            "total_tokens": row["total_tokens"],
            "cost_usd": row["cost_usd"],
            "model": model,
            "daily": {
                "prompt_tokens": summary["prompt_tokens"],
                "completion_tokens": summary["completion_tokens"],
                "total_tokens": summary["total_tokens"],
                "cost_usd": summary["cost_usd"],
                "budget_usd": summary["budget_usd"],
                "remaining_usd": summary["remaining_usd"],
                "calls": summary["calls"],
            },
        }


class ToolExecutorAdapter:
    def __init__(self, registry=None):
        self._registry = registry

    def _reg(self):
        if self._registry is None:
            from backend.tools import get_tool_registry

            self._registry = get_tool_registry()
        return self._registry

    def openai_definitions(self) -> List[Dict[str, Any]]:
        from backend.tools import get_openai_tool_definitions

        return get_openai_tool_definitions()

    async def execute_calls(
        self,
        tool_calls: list,
        *,
        context: Optional[Dict[str, Any]] = None,
        max_calls: int = 5,
    ) -> List[Dict[str, Any]]:
        reg = self._reg()
        # 暫調上限
        old = reg.max_tools_per_turn
        reg.max_tools_per_turn = max_calls
        try:
            results = await reg.execute_openai_tool_calls(
                tool_calls, context=context or {}
            )
        finally:
            reg.max_tools_per_turn = old
        out = []
        for tr in results:
            out.append(
                {
                    "name": tr.name,
                    "display_name": tr.display_name,
                    "icon": tr.icon,
                    "ok": tr.ok,
                    "duration_ms": tr.duration_ms,
                    "arguments": tr.arguments,
                    "error": tr.error,
                    "error_code": tr.error_code,
                    "tool_call_id": tr.tool_call_id,
                    "content": tr.content,
                }
            )
        return out


class VoiceHintAdapter:
    def build_hint(self, *, voice_mode: bool, car_mode: bool) -> str:
        try:
            from backend.voice_router import build_voice_system_hint

            return build_voice_system_hint(
                voice_mode=voice_mode or car_mode, car_mode=car_mode
            )
        except Exception:
            return ""


class SpeechSanitizeAdapter:
    def sanitize(self, text: str) -> str:
        try:
            from backend.voice_router import sanitize_for_speech

            speech, _ = sanitize_for_speech(text or "", strip_emojis=True, max_chars=800)
            return speech
        except Exception:
            return (text or "")[:800]


class PostProcessAdapter:
    def __init__(self, memory_adapter: MemoryAdapter):
        self.memory = memory_adapter

    async def run_jobs(self, jobs: list) -> None:
        async def save(job: PostProcessJob):
            await self.memory.save(
                job.conversation_id,
                job.user_message,
                job.assistant_message,
                job.emotion_analysis,
                ai_id=job.ai_id,
                user_id=job.user_id,
            )

        await run_post_process(jobs, memory_save_fn=save, shadow=False)


def build_default_deps(
    *,
    memory_system,
    prompt_engine,
    redis_interface,
    openai_client,
    tracker,
    model_gateway=None,
) -> KernelDeps:
    from backend.ai_kernel.model_gateway import OpenAIModelGateway

    mem = MemoryAdapter(memory_system)
    return KernelDeps(
        memory=mem,
        files=FileContextAdapter(redis_interface),
        prompt=PromptAdapter(prompt_engine),
        moderation=ModerationAdapter(openai_client),
        budget=BudgetAdapter(tracker),
        model=model_gateway or OpenAIModelGateway(),
        tools=ToolExecutorAdapter(),
        voice=VoiceHintAdapter(),
        speech=SpeechSanitizeAdapter(),
        post_process=PostProcessAdapter(mem),
    )
