"""
AIKernel 主入口 — 協調 Pipeline / Planner / AgentLoop / PostProcess。
不依賴 FastAPI Request、不直接使用 OpenAI SDK、不使用全域 DB。
"""
from __future__ import annotations

import logging
from typing import Any, AsyncIterator, Dict, Optional

from backend.ai_kernel.context import assemble_context
from backend.ai_kernel.errors import (
    BudgetExceededError,
    KernelFatalError,
    ModerationBlockedError,
    ModelGatewayError,
)
from backend.ai_kernel.feature_flags import KernelFlags, get_kernel_flags
from backend.ai_kernel.models import (
    KernelEvent,
    KernelRequest,
    KernelResult,
    PlanAction,
)
from backend.ai_kernel.pipeline import RequestPipeline
from backend.ai_kernel.planner import plan_request
from backend.ai_kernel.ports import KernelDeps
from backend.ai_kernel.post_process import build_post_process_jobs, should_skip_memory_write
from backend.ai_kernel.strategies import select_response_strategy
from backend.ai_kernel.tool_policy import AgentLoop, ToolPolicy
from backend.ai_kernel.tracing import KernelTrace, store_trace

logger = logging.getLogger("ai_kernel")


class AIKernel:
    def __init__(self, deps: KernelDeps, flags: Optional[KernelFlags] = None):
        self.deps = deps
        self.flags = flags or get_kernel_flags()

    async def run(self, request: KernelRequest) -> KernelResult:
        """非串流完整執行。"""
        trace = KernelTrace(
            request_id=request.request_id,
            enabled=self.flags.debug_enabled,
        )
        state: Dict[str, Any] = {"request": request, "trace": trace}

        pipeline = (
            RequestPipeline(trace=trace)
            .add("budget", self._stage_budget)
            .add("moderation", self._stage_moderation)
            .add("load_context_sources", self._stage_load_sources)
            .add("build_prompt", self._stage_build_prompt)
            .add("plan", self._stage_plan)
            .add("strategy", self._stage_strategy)
            .add("assemble_context", self._stage_assemble)
            .add("generate", self._stage_generate)
            .add("post_process_plan", self._stage_post_plan)
        )
        try:
            state = await pipeline.run(state)
        except (BudgetExceededError, ModerationBlockedError):
            raise
        except Exception as e:
            logger.warning("kernel fatal: %s", type(e).__name__)
            raise KernelFatalError(type(e).__name__) from e
        finally:
            store_trace(trace)

        result: KernelResult = state["result"]
        result.trace_id = trace.trace_id

        # 副作用（shadow 跳過）
        if (
            not request.shadow
            and not self.flags.shadow_mode
            and result.post_process_jobs
            and self.deps.post_process
        ):
            try:
                await self.deps.post_process.run_jobs(result.post_process_jobs)
            except Exception as e:
                logger.warning("post_process failed: %s", type(e).__name__)

        return result

    async def run_stream(self, request: KernelRequest) -> AsyncIterator[KernelEvent]:
        """
        串流：先跑前置 stages，再 stream tokens，最後 post_process。
        yield KernelEvent（Router 再轉協議）。
        """
        trace = KernelTrace(
            request_id=request.request_id, enabled=self.flags.debug_enabled
        )
        state: Dict[str, Any] = {"request": request, "trace": trace}
        pipeline = (
            RequestPipeline(trace=trace)
            .add("budget", self._stage_budget)
            .add("moderation", self._stage_moderation)
            .add("load_context_sources", self._stage_load_sources)
            .add("build_prompt", self._stage_build_prompt)
            .add("plan", self._stage_plan)
            .add("strategy", self._stage_strategy)
            .add("assemble_context", self._stage_assemble)
        )
        try:
            state = await pipeline.run(state)
        except BudgetExceededError:
            raise
        except ModerationBlockedError as e:
            yield KernelEvent(type="content", text=str(e.message or "blocked"))
            yield KernelEvent(
                type="usage",
                data={"blocked": True, "usage": {}},
            )
            store_trace(trace)
            return
        except Exception as e:
            store_trace(trace)
            raise KernelFatalError(type(e).__name__) from e

        ctx = state["context"]
        tools_used = []
        usage_acc = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        full = ""

        # Tool phase (non-stream) then stream final
        try:
            if ctx.plan and ctx.plan.allow_tools and request.use_tools:
                loop = AgentLoop(
                    self.deps.model,
                    self.deps.tools,
                    ToolPolicy(self.flags),
                    trace=trace,
                )
                # 若 plan 要用工具：先 agent loop 非串流拿最終內容
                out = await loop.run(ctx, user_id=request.user_id)
                for ev in out.get("events") or []:
                    yield KernelEvent(
                        type="tool_status",
                        status=ev.get("status") or "",
                        text=ev.get("message") or "",
                        data=ev,
                    )
                full = out.get("content") or ""
                tools_used = out.get("tools_used") or []
                usage_acc = out.get("usage") or usage_acc
                if full:
                    yield KernelEvent(type="content", text=full)
            else:
                yield KernelEvent(
                    type="tool_status",
                    status="skipped",
                    text="本次無需使用工具",
                    data={"status": "skipped", "tools": []},
                )
                async for event in self.deps.model.stream(
                    ctx.messages,
                    model=ctx.model_config_obj.model,
                    temperature=ctx.strategy.temperature,
                    max_tokens=ctx.strategy.max_tokens,
                ):
                    if event.get("type") == "content":
                        t = event.get("text") or ""
                        full += t
                        yield KernelEvent(type="content", text=t)
                    elif event.get("type") == "usage":
                        usage_acc = event.get("usage") or usage_acc
        except Exception as e:
            err = f"[ERROR] Streaming 失敗: {type(e).__name__}"
            full = err
            yield KernelEvent(type="content", text=err)

        # usage record
        usage_payload = {}
        try:
            if not request.shadow and not self.flags.shadow_mode:
                usage_payload = self.deps.budget.record(
                    user_id=request.user_id,
                    conversation_id=request.conversation_id,
                    model=ctx.model_config_obj.model,
                    usage=usage_acc,
                    endpoint="chat_stream_kernel",
                    meta={"kernel": True},
                )
        except Exception:
            usage_payload = usage_acc

        speech = None
        if request.voice_mode or request.car_mode or request.speak_response:
            speech = self.deps.speech.sanitize(full)

        result = KernelResult(
            assistant_message=full,
            emotion_analysis=ctx.emotion_analysis,
            conversation_id=request.conversation_id,
            usage=usage_payload,
            tools_used=tools_used,
            speech_text=speech,
            plan=ctx.plan,
            used_kernel=True,
            blocked=False,
            trace_id=trace.trace_id,
        )
        result.post_process_jobs = build_post_process_jobs(
            result,
            request_id=request.request_id or trace.trace_id,
            user_id=request.user_id,
            user_message=request.user_message,
            ai_id=request.ai_id,
            shadow=request.shadow or self.flags.shadow_mode,
        )

        yield KernelEvent(
            type="usage",
            data={
                "blocked": False,
                "usage": usage_payload,
                "tools_used": tools_used,
                "speech_text": speech,
                "voice_mode": request.voice_mode,
                "car_mode": request.car_mode,
                "kernel": True,
                "trace_id": trace.trace_id,
            },
        )

        if (
            not request.shadow
            and not self.flags.shadow_mode
            and result.post_process_jobs
            and self.deps.post_process
            and not should_skip_memory_write(full)
        ):
            try:
                await self.deps.post_process.run_jobs(result.post_process_jobs)
            except Exception as e:
                logger.warning("stream post_process failed: %s", type(e).__name__)

        store_trace(trace)

    # --- stages ---

    async def _stage_budget(self, state: dict) -> dict:
        req: KernelRequest = state["request"]
        ok, reason, ctx = self.deps.budget.check(req.user_id)
        if not ok:
            raise BudgetExceededError(reason)
        state["budget_ctx"] = ctx
        return state

    async def _stage_moderation(self, state: dict) -> dict:
        req: KernelRequest = state["request"]
        mod = await self.deps.moderation.check(req.user_message)
        if mod.get("blocked"):
            from backend.moderation import format_block_message

            raise ModerationBlockedError(format_block_message(mod))
        state["moderation"] = mod
        return state

    async def _stage_load_sources(self, state: dict) -> dict:
        req: KernelRequest = state["request"]
        try:
            memories = await self.deps.memory.recall(
                req.user_message, req.conversation_id, req.user_id
            )
        except Exception:
            memories = ""
        try:
            history = self.deps.memory.history(req.conversation_id, limit=5)
        except Exception:
            history = ""
        try:
            files = self.deps.files.get_file_content(req.conversation_id)
        except Exception:
            files = ""
        state["recalled_memories"] = memories or ""
        state["conversation_history"] = history or ""
        state["file_content"] = files or ""
        return state

    async def _stage_build_prompt(self, state: dict) -> dict:
        req: KernelRequest = state["request"]
        messages, emotion = await self.deps.prompt.build(
            req.user_message,
            state.get("recalled_memories") or "",
            state.get("conversation_history") or "",
            state.get("file_content") or "",
        )
        system = ""
        if messages and messages[0].get("role") == "system":
            system = messages[0].get("content") or ""
        state["system_prompt"] = system
        state["emotion_analysis"] = emotion or {}
        state["raw_messages"] = messages
        return state

    async def _stage_plan(self, state: dict) -> dict:
        req: KernelRequest = state["request"]
        state["plan"] = plan_request(req, use_tools=req.use_tools)
        return state

    async def _stage_strategy(self, state: dict) -> dict:
        req: KernelRequest = state["request"]
        cfg, strategy = select_response_strategy(req)
        state["model_config"] = cfg
        state["strategy"] = strategy
        return state

    async def _stage_assemble(self, state: dict) -> dict:
        req: KernelRequest = state["request"]
        voice_hint = ""
        if req.voice_mode or req.car_mode:
            voice_hint = self.deps.voice.build_hint(
                voice_mode=req.voice_mode, car_mode=req.car_mode
            )
        ctx = assemble_context(
            req,
            system_prompt=state.get("system_prompt") or "",
            recalled_memories=state.get("recalled_memories") or "",
            conversation_history=state.get("conversation_history") or "",
            file_content=state.get("file_content") or "",
            voice_hint=voice_hint,
            emotion_analysis=state.get("emotion_analysis") or {},
            token_budget=self.flags.context_token_budget,
        )
        ctx.plan = state.get("plan")
        ctx.model_config_obj = state["model_config"]
        ctx.strategy = state["strategy"]
        # 若 prompt 已有完整 messages，優先用 budget 裁過的；否則用 raw
        if not ctx.messages:
            ctx.messages = state.get("raw_messages") or []
        state["context"] = ctx
        return state

    async def _stage_generate(self, state: dict) -> dict:
        req: KernelRequest = state["request"]
        ctx = state["context"]
        loop = AgentLoop(
            self.deps.model,
            self.deps.tools,
            ToolPolicy(self.flags),
            trace=state.get("trace"),
        )
        out = await loop.run(ctx, user_id=req.user_id)
        content = out.get("content") or ""
        usage = out.get("usage") or {}
        tools_used = out.get("tools_used") or []

        usage_payload = {}
        if not req.shadow and not self.flags.shadow_mode:
            try:
                usage_payload = self.deps.budget.record(
                    user_id=req.user_id,
                    conversation_id=req.conversation_id,
                    model=ctx.model_config_obj.model,
                    usage=usage,
                    endpoint="chat_kernel",
                    meta={"kernel": True},
                )
            except Exception:
                usage_payload = usage

        speech = None
        if req.voice_mode or req.car_mode or req.speak_response:
            speech = self.deps.speech.sanitize(content)

        events = [
            KernelEvent(
                type="tool_status",
                status=ev.get("status") or "",
                text=ev.get("message") or "",
                data=ev,
            )
            for ev in (out.get("events") or [])
        ]
        result = KernelResult(
            assistant_message=content,
            emotion_analysis=ctx.emotion_analysis,
            conversation_id=req.conversation_id,
            usage=usage_payload,
            tools_used=tools_used,
            speech_text=speech,
            events=events,
            plan=ctx.plan,
            used_kernel=True,
        )
        state["result"] = result
        return state

    async def _stage_post_plan(self, state: dict) -> dict:
        req: KernelRequest = state["request"]
        result: KernelResult = state["result"]
        result.post_process_jobs = build_post_process_jobs(
            result,
            request_id=req.request_id or result.trace_id,
            user_id=req.user_id,
            user_message=req.user_message,
            ai_id=req.ai_id,
            shadow=req.shadow or self.flags.shadow_mode,
        )
        return state


async def run_kernel_chat(
    request: KernelRequest,
    deps: KernelDeps,
    flags: Optional[KernelFlags] = None,
) -> KernelResult:
    return await AIKernel(deps, flags=flags).run(request)
