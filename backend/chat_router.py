import asyncio # ✅ 新增匯入，用於後台任務
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query # ✅ 匯入 BackgroundTasks, Query
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
import os
import logging
import json
import traceback # 確保 traceback 也在

# *** 請確保這些模組在你的 backend/ 目錄中可被正確匯入 ***
from backend.supabase_handler import get_supabase
supabase = get_supabase()
from backend.openai_handler import get_openai_client, generate_response, generate_response_stream, generate_response_with_tools
from backend.prompt_engine import PromptEngine
from modules.memory_system import MemorySystem
from backend.redis_interface import RedisInterface
from backend.core_controller import get_core_controller
from backend.tools import get_tool_registry, get_openai_tool_definitions
from backend.token_tracker import get_token_tracker, estimate_cost_usd
from backend.moderation import moderate_text, format_block_message

router = APIRouter()
logger = logging.getLogger("chat_router")
redis_interface = RedisInterface()

# 串流事件 / 用量 meta 標記（前端可解析）
USAGE_META_PREFIX = "\n__XCG_META__"
TOOL_EVENT_PREFIX = "__XCG_EVENT__"

_reflection_storage = None


def get_reflection_storage():
    """獲取反思儲存服務（延遲初始化）"""
    global _reflection_storage
    if _reflection_storage is None:
        try:
            from backend.modules.reflection_storage import ReflectionStorage
            from backend.modules.pinecone_handler import PineconeHandler

            _reflection_storage = ReflectionStorage(
                redis_interface=RedisInterface(),
                supabase_client=supabase,
                pinecone_handler=PineconeHandler()
            )
            logger.info("✅ 反思儲存服務已啟用")
        except Exception as e:
            logger.warning(f"⚠️ 反思儲存服務初始化失敗: {e}")
            _reflection_storage = None
    return _reflection_storage


# =========================================================
# ✅ 數據模型（已新增 AI 寶貝切換開關）
# =========================================================
class ChatRequest(BaseModel):
    user_message: str
    conversation_id: str
    user_id: str = "default_user"
    # ✅ 新增 AI 寶貝切換開關
    ai_id: str = os.getenv("AI_ID", "xiaochenguang_v1")
    # 🎙️ 語音 / 車載
    voice_mode: bool = False  # 語音友善回覆（簡短口語）
    car_mode: bool = False  # 車載：更短、重點前置
    input_method: str = "text"  # text | voice
    speak_response: bool = False  # 前端是否會朗讀（供後端日誌/策略）
    
class ChatResponse(BaseModel):
    assistant_message: str
    emotion_analysis: dict
    conversation_id: str
    reflection: Optional[dict] = None
    usage: Optional[dict] = None
    usage_summary: Optional[dict] = None
    tools_used: Optional[list] = None
    speech_text: Optional[str] = None  # TTS 友善純文字


def _tool_event_payload(
    status: str,
    results_or_calls=None,
    *,
    step: Optional[int] = None,
    total: Optional[int] = None,
    message: str = "",
    tools: Optional[list] = None,
) -> str:
    """產生前端可解析的工具狀態事件行。"""
    tool_list = list(tools or [])
    if not tool_list:
        for item in results_or_calls or []:
            if hasattr(item, "name"):
                # ToolCallResult
                tool_list.append(
                    {
                        "name": item.name,
                        "display_name": getattr(item, "display_name", None) or item.name,
                        "icon": getattr(item, "icon", "🔧"),
                        "ok": getattr(item, "ok", None),
                        "duration_ms": getattr(item, "duration_ms", None),
                        "arguments": getattr(item, "arguments", {}) or {},
                        "error": getattr(item, "error", None),
                        "error_code": getattr(item, "error_code", None),
                        "index": getattr(item, "index", None),
                        "total": getattr(item, "total", None),
                        "phase": "done" if getattr(item, "ok", None) is not None else "pending",
                    }
                )
            elif isinstance(item, dict):
                tool_list.append(item)
            else:
                # raw openai tool_call
                try:
                    name = item.function.name
                    args_raw = item.function.arguments or "{}"
                    args = json.loads(args_raw) if isinstance(args_raw, str) else dict(args_raw)
                except Exception:
                    name = "unknown"
                    args = {}
                tool_list.append(
                    {
                        "name": name,
                        "display_name": name,
                        "arguments": args,
                        "ok": None,
                        "phase": "pending",
                    }
                )
    payload = {
        "type": "tool_status",
        "status": status,
        "tools": tool_list,
        "step": step,
        "total": total if total is not None else len(tool_list),
        "message": message,
    }
    return TOOL_EVENT_PREFIX + json.dumps(payload, ensure_ascii=False)


def _merge_usage(*usages: Optional[Dict[str, Any]]) -> Dict[str, int]:
    total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    for u in usages:
        if not u:
            continue
        total["prompt_tokens"] += int(u.get("prompt_tokens") or 0)
        total["completion_tokens"] += int(u.get("completion_tokens") or 0)
        total["total_tokens"] += int(
            u.get("total_tokens")
            or (int(u.get("prompt_tokens") or 0) + int(u.get("completion_tokens") or 0))
        )
    return total


def _record_usage(
    *,
    user_id: str,
    conversation_id: str,
    model: str,
    usage: Optional[Dict[str, Any]],
    endpoint: str = "chat",
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    tracker = get_token_tracker()
    u = usage or {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    row = tracker.record(
        user_id=user_id,
        conversation_id=conversation_id,
        model=model,
        prompt_tokens=int(u.get("prompt_tokens") or 0),
        completion_tokens=int(u.get("completion_tokens") or 0),
        total_tokens=int(u.get("total_tokens") or 0) or None,
        endpoint=endpoint,
        meta=meta,
    )
    summary = tracker.get_user_daily_summary(user_id)
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


# =========================================================
# ✅ 核心：【隱形後門通道】的處理函數 (Background Task Function)
# =========================================================
async def run_post_chat_tasks(
    request: ChatRequest, assistant_message: str, emotion_analysis: dict
):
    """
    此函數負責所有耗時的、不影響即時回覆的後續處理工作：
    反思、行為調節、三層記憶儲存等。
    """
    logger.info(f"🟢 啟動背景處理任務，處理 conversation_id: {request.conversation_id}")
    
    # 重新實例化或獲取必要的服務
    openai_client = get_openai_client()
    memories_table = os.getenv("SUPABASE_MEMORIES_TABLE", "xiaochenguang_memories")
    memory_system = MemorySystem(supabase, openai_client, memories_table)
    prompt_engine = PromptEngine(
        request.conversation_id, memories_table, user_id=request.user_id
    )
    
    reflection_result = None
    
    try:
        controller = await get_core_controller()
        
        # 額外：將即時儲存也放入背景，只在回覆後執行
        await memory_system.save_emotional_state(
            request.user_id,
            emotion_analysis,
            context=request.user_message
        )
        prompt_engine.personality_engine.learn_from_interaction(
            request.user_message,
            assistant_message,
            emotion_analysis
        )
        await asyncio.to_thread(prompt_engine.personality_engine.save_personality) # 確保同步寫入被安全處理
        
        # === 階段1：反思分析 ===
        reflection_module = await controller.get_module("reflection")
        if reflection_module:
            reflection_response = await reflection_module.process({
                "user_message": request.user_message,
                "assistant_message": assistant_message,
                "emotion_analysis": emotion_analysis
            })
            
            if reflection_response.get("success"):
                reflection_result = reflection_response.get("reflection")
                logger.info(f"🧠 背景：反思完成（置信度: {reflection_result.get('confidence', 0):.2f}）")
                
                # === 階段1.5：反思儲存（三層架構）===
                reflection_storage = get_reflection_storage()
                if reflection_storage and reflection_result:
                    storage_result = await reflection_storage.store_reflection(
                        reflection_data=reflection_result,
                        conversation_id=request.conversation_id,
                        user_id=request.user_id,
                        related_message_id=None
                    )
                    if storage_result.get("overall_success"):
                        logger.info(f"💾 背景：反思已儲存到三層架構")
                    else:
                        logger.warning(f"⚠️ 背景：反思儲存部分失敗")
                
                # === 階段2：行為調節（基於反思結果）===
                behavior_module = await controller.get_module("behavior")
                if behavior_module and reflection_result:
                    behavior_response = await behavior_module.process({
                        "reflection": reflection_result,
                        "emotion_analysis": emotion_analysis,
                        "conversation_context": {
                            "user_message": request.user_message,
                            "assistant_message": assistant_message
                        }
                    })
                    if behavior_response.get("success"):
                        logger.info(f"🎯 背景：人格調整已完成")

        # === 階段3：以統一 MemorySystem 更新短期快取（含反思）===
        if reflection_result:
            memory_system._cache_short_term(
                conversation_id=request.conversation_id,
                user_id=request.user_id,
                user_input=request.user_message,
                bot_response=assistant_message,
                reflection=reflection_result,
            )
            logger.info("💾 背景：已將反思寫入短期記憶快取")

    except Exception as e:
        logger.warning(f"⚠️ 背景任務處理失敗: {e}", exc_info=True)


async def _try_kernel_chat(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    *,
    stream: bool,
    use_tools: bool,
):
    """
    Strangler 入口：AI_KERNEL_ENABLED 時使用 Kernel。
    回傳 Response 或 None（表示改走 Legacy）。
    Shadow 模式：並行跑 Kernel 但不取代回應、無副作用。
    """
    try:
        from backend.ai_kernel.feature_flags import get_kernel_flags
        from backend.ai_kernel.models import KernelRequest
        from backend.ai_kernel.kernel import AIKernel
        from backend.ai_kernel.adapters import build_default_deps
        from backend.ai_kernel.errors import (
            BudgetExceededError,
            KernelFatalError,
            ModerationBlockedError,
        )
        from backend.logging_utils import get_request_id
    except Exception as e:
        logger.warning("Kernel import failed, legacy only: %s", e)
        return None

    flags = get_kernel_flags()
    if not flags.enabled and not flags.shadow_mode:
        return None

    openai_client = get_openai_client()
    memories_table = os.getenv("SUPABASE_MEMORIES_TABLE", "xiaochenguang_memories")
    tracker = get_token_tracker()
    memory_system = MemorySystem(supabase, openai_client, memories_table)
    prompt_engine = PromptEngine(
        request.conversation_id, memories_table, user_id=request.user_id
    )
    deps = build_default_deps(
        memory_system=memory_system,
        prompt_engine=prompt_engine,
        redis_interface=redis_interface,
        openai_client=openai_client,
        tracker=tracker,
    )
    kreq = KernelRequest(
        user_message=request.user_message,
        conversation_id=request.conversation_id,
        user_id=request.user_id,
        ai_id=request.ai_id,
        voice_mode=request.voice_mode,
        car_mode=request.car_mode,
        input_method=request.input_method,
        speak_response=request.speak_response,
        use_tools=use_tools,
        stream=stream,
        request_id=get_request_id() or "",
        shadow=flags.shadow_mode and not flags.enabled,
    )

    # Shadow：背景執行，主路徑仍 Legacy；強制 shadow=True（無記憶/token/真實工具）
    if flags.shadow_mode and not flags.enabled:
        async def _shadow():
            try:
                kreq.shadow = True
                # shadow 使用同一 flags，kernel 內部會禁止副作用
                await AIKernel(deps, flags=flags).run(kreq)
                logger.info(
                    "🌑 Kernel shadow ok conv=%s (no side effects)",
                    request.conversation_id[:8],
                )
            except Exception as ex:
                logger.info("🌑 Kernel shadow failed: %s", type(ex).__name__)

        background_tasks.add_task(_shadow)
        return None

    # Enabled path
    kernel = AIKernel(deps, flags=flags)
    try:
        if stream:
            async def stream_gen():
                try:
                    async for ev in kernel.run_stream(kreq):
                        if ev.type == "content" and ev.text:
                            yield ev.text
                        elif ev.type == "tool_status":
                            payload = {
                                "type": "tool_status",
                                "status": ev.status or ev.data.get("status") or "",
                                "tools": ev.data.get("tools") or [],
                                "step": ev.data.get("step"),
                                "total": ev.data.get("total"),
                                "message": ev.text or ev.data.get("message") or "",
                            }
                            yield TOOL_EVENT_PREFIX + json.dumps(
                                payload, ensure_ascii=False
                            ) + "\n"
                        elif ev.type == "usage":
                            meta = dict(ev.data or {})
                            yield USAGE_META_PREFIX + json.dumps(
                                meta, ensure_ascii=False
                            )
                except BudgetExceededError as be:
                    yield f"[ERROR] budget_exceeded: {be.message}"
                except ModerationBlockedError as me:
                    yield me.message or "內容未通過安全審核"
                    yield USAGE_META_PREFIX + json.dumps(
                        {"blocked": True, "usage": {}}, ensure_ascii=False
                    )
                except Exception as ex:
                    if flags.fallback_to_legacy_on_fatal:
                        logger.warning(
                            "Kernel stream fatal → client error (legacy not mid-stream): %s",
                            type(ex).__name__,
                        )
                    yield f"[ERROR] Kernel: {type(ex).__name__}"

            return StreamingResponse(
                stream_gen(),
                media_type="text/plain; charset=utf-8",
                headers={
                    "Cache-Control": "no-cache, no-transform",
                    "X-Accel-Buffering": "no",
                    "Connection": "keep-alive",
                    "X-AI-Kernel": "1",
                },
            )

        # non-stream
        result = await kernel.run(kreq)
        return ChatResponse(
            assistant_message=result.assistant_message,
            emotion_analysis=result.emotion_analysis or {},
            conversation_id=request.conversation_id,
            reflection=None,
            speech_text=result.speech_text,
            usage=result.usage,
            usage_summary=(result.usage or {}).get("daily"),
            tools_used=result.tools_used or None,
        )
    except BudgetExceededError as be:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "budget_exceeded",
                "message": be.message,
            },
        )
    except ModerationBlockedError as me:
        return JSONResponse(
            status_code=400,
            content={"error": "content_blocked", "message": me.message},
        )
    except (KernelFatalError, Exception) as e:
        if flags.fallback_to_legacy_on_fatal:
            logger.warning(
                "Kernel fatal → fallback legacy: %s", type(e).__name__
            )
            return None
        raise HTTPException(status_code=500, detail="Kernel error")


# =========================================================
# ✅ 主流程：/chat 路由（支援 stream=true 真實 OpenAI 串流）
# =========================================================
@router.post("/chat")
async def chat(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    stream: bool = Query(default=True, description="是否使用 OpenAI streaming 即時回傳"),
    use_tools: bool = Query(default=True, description="串流前是否允許 tool calling（如 web_search）"),
):
    try:
        logger.info(f"🟢 接收到聊天請求，conversation_id: {request.conversation_id}, stream={stream}")

        # --- AI Kernel (Strangler)：flag 開啟時走新核心，失敗可回退 Legacy ---
        kernel_response = await _try_kernel_chat(
            request, background_tasks, stream=stream, use_tools=use_tools
        )
        if kernel_response is not None:
            return kernel_response

        openai_client = get_openai_client()
        memories_table = os.getenv("SUPABASE_MEMORIES_TABLE", "xiaochenguang_memories")
        tracker = get_token_tracker()

        # --- 成本控制：預算檢查 ---
        allowed, budget_reason, budget_ctx = tracker.check_budget(request.user_id)
        if not allowed:
            logger.warning(f"⛔ 預算攔截 user={request.user_id[:8]}... {budget_reason}")
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "budget_exceeded",
                    "message": budget_reason,
                    "usage": budget_ctx.get("user"),
                },
            )

        # --- 內容安全審核（輸入）---
        moderation = await moderate_text(request.user_message, client=openai_client)
        if moderation.get("blocked"):
            msg = format_block_message(moderation)
            logger.warning(
                f"🚫 使用者訊息被審核攔截 conv={request.conversation_id[:8]}..."
            )
            if stream:
                async def blocked_stream():
                    yield msg
                    meta = {
                        "blocked": True,
                        "moderation": {
                            "flagged": moderation.get("flagged"),
                            "flagged_categories": moderation.get("flagged_categories"),
                        },
                        "usage": {
                            "prompt_tokens": 0,
                            "completion_tokens": 0,
                            "total_tokens": 0,
                            "cost_usd": 0,
                            "model": "none",
                        },
                    }
                    yield USAGE_META_PREFIX + json.dumps(meta, ensure_ascii=False)

                return StreamingResponse(
                    blocked_stream(),
                    media_type="text/plain; charset=utf-8",
                    headers={
                        "Cache-Control": "no-cache, no-transform",
                        "X-Content-Moderation": "blocked",
                    },
                )
            return JSONResponse(
                status_code=400,
                content={
                    "error": "content_blocked",
                    "message": msg,
                    "moderation": {
                        "flagged": moderation.get("flagged"),
                        "flagged_categories": moderation.get("flagged_categories"),
                    },
                },
            )

        memory_system = MemorySystem(supabase, openai_client, memories_table)
        prompt_engine = PromptEngine(
            request.conversation_id, memories_table, user_id=request.user_id
        )

        # 1. 執行所有「讀取」任務（必須在串流前完成）
        recalled_memories = await memory_system.recall_memories(
            request.user_message,
            request.conversation_id,
            user_id=request.user_id
        )
        conversation_history = memory_system.get_conversation_history(
            request.conversation_id,
            limit=5
        )

        # Retrieve file / vision content from Redis
        file_content = ""
        try:
            if redis_interface.redis:
                keys = redis_interface.redis.keys(f"upload:{request.conversation_id}:*")
                if keys:
                    latest_key = keys[-1]
                    file_data_json = redis_interface.redis.get(latest_key)
                    if file_data_json:
                        file_data = json.loads(file_data_json)
                        file_content = (
                            file_data.get("vision_analysis")
                            or file_data.get("content")
                            or ""
                        )
                        if file_data.get("is_image"):
                            fname = file_data.get("file_name") or "image"
                            file_content = (
                                f"【使用者上傳圖片：{fname}】\n"
                                f"視覺分析：\n{file_content}"
                            )
                        logger.info(f"📄 成功從 Redis 檢索檔案內容: {latest_key}")
        except Exception as e:
            logger.warning(f"⚠️ 從 Redis 檢索檔案內容失敗: {e}")

        messages, emotion_analysis = await prompt_engine.build_prompt(
            request.user_message,
            recalled_memories,
            conversation_history,
            file_content
        )

        # 🎙️ 語音 / 車載：注入口語化、可朗讀的回覆規範
        if request.voice_mode or request.car_mode:
            try:
                from backend.voice_router import build_voice_system_hint

                voice_hint = build_voice_system_hint(
                    voice_mode=request.voice_mode or request.car_mode,
                    car_mode=request.car_mode,
                )
                if voice_hint and messages and messages[0].get("role") == "system":
                    messages[0]["content"] = (
                        f"{messages[0].get('content', '')}\n\n{voice_hint}"
                    )
                logger.info(
                    "🎙️ 語音模式已啟用 voice_mode=%s car_mode=%s input=%s",
                    request.voice_mode,
                    request.car_mode,
                    request.input_method,
                )
            except Exception as e:
                logger.warning(f"⚠️ 注入語音提示失敗: {e}")

        # ✅ 根據 AI ID 選擇模型
        if request.ai_id == "story_master_v1":
            selected_model = "gpt-4o"
            selected_temperature = 0.95
            logger.info("✨ 啟用：Story Master 故事光光寶貝")
        else:
            selected_model = "gpt-4o-mini"
            selected_temperature = 0.8
            logger.info("🌟 啟用：Xiaochenguang 預設光光寶貝")

        # 車載模式：略降 max_tokens，回覆更短、更快
        voice_max_tokens = 600 if request.car_mode else (800 if request.voice_mode else 2000)
        stream_max_tokens = 800 if request.car_mode else (1200 if request.voice_mode else 2000)

        # =========================================================
        # ✅ Streaming 模式：OpenAI stream=True 真實 token 串流
        # - 預設直接串流（低延遲、即時打字）
        # - use_tools=true 時：先非串流 tool calling，再 stream 最終答案
        # =========================================================
        if stream:
            async def _post_stream_tasks(full_response: str):
                """串流結束後：記憶儲存 + 反思等背景任務"""
                if not full_response or full_response.startswith("[ERROR]"):
                    return
                try:
                    await memory_system.save_memory(
                        request.conversation_id,
                        request.user_message,
                        full_response,
                        emotion_analysis,
                        ai_id=request.ai_id,
                        user_id=request.user_id,
                    )
                    logger.info("💾 Streaming 後記憶儲存完成")
                except Exception as e:
                    logger.warning(f"⚠️ Streaming 後記憶儲存失敗: {e}")
                try:
                    await run_post_chat_tasks(request, full_response, emotion_analysis)
                except Exception as e:
                    logger.warning(f"⚠️ Streaming 後背景任務失敗: {e}")

            async def stream_generator():
                full_response = ""
                stream_usage = None
                tool_usage = None
                tools_used_meta = []
                final_messages = messages
                try:
                    # --- Tool calling 階段（逐步推送狀態）---
                    if use_tools:
                        try:
                            registry = get_tool_registry()
                            tool_defs = get_openai_tool_definitions()
                            if tool_defs:
                                yield _tool_event_payload(
                                    "planning",
                                    message="正在判斷是否需要使用工具…",
                                    tools=[],
                                ) + "\n"

                                tool_response = await generate_response_with_tools(
                                    messages,
                                    tools=tool_defs,
                                    model=selected_model,
                                    temperature=selected_temperature,
                                    max_tokens=1000,
                                )
                                tool_usage = tool_response.get("usage")

                                if (
                                    tool_response.get("finish_reason") == "tool_calls"
                                    and tool_response.get("tool_calls")
                                ):
                                    logger.info(
                                        f"🔧 [Streaming] 工具呼叫 x{len(tool_response['tool_calls'])}"
                                    )
                                    final_messages = list(messages)
                                    final_messages.append(tool_response["raw_message"])

                                    live_tools = []
                                    tool_results = []
                                    ctx = {"user_id": request.user_id}

                                    async for step in registry.iter_openai_tool_calls(
                                        tool_response["tool_calls"],
                                        context=ctx,
                                    ):
                                        if step.get("type") == "start":
                                            live_tools.append(
                                                {
                                                    "name": step.get("name"),
                                                    "display_name": step.get("display_name")
                                                    or step.get("name"),
                                                    "icon": step.get("icon") or "🔧",
                                                    "arguments": step.get("arguments") or {},
                                                    "ok": None,
                                                    "phase": "running",
                                                    "index": step.get("index"),
                                                    "total": step.get("total"),
                                                }
                                            )
                                            yield _tool_event_payload(
                                                "running",
                                                tools=live_tools,
                                                step=(step.get("index") or 0) + 1,
                                                total=step.get("total"),
                                                message=f"正在執行：{step.get('display_name') or step.get('name')}",
                                            ) + "\n"
                                        elif step.get("type") == "result":
                                            tr = step["result"]
                                            tool_results.append(tr)
                                            # 更新 live 列表對應項目
                                            for t in live_tools:
                                                if t.get("name") == tr.name and t.get("phase") == "running":
                                                    t["ok"] = tr.ok
                                                    t["phase"] = "done" if tr.ok else "error"
                                                    t["duration_ms"] = tr.duration_ms
                                                    t["error"] = tr.error
                                                    t["display_name"] = tr.display_name or t.get("display_name")
                                                    t["icon"] = tr.icon or t.get("icon")
                                                    break
                                            final_messages.append(
                                                {
                                                    "role": "tool",
                                                    "tool_call_id": tr.tool_call_id,
                                                    "content": tr.content,
                                                }
                                            )
                                            yield _tool_event_payload(
                                                "progress",
                                                tools=live_tools,
                                                step=len(tool_results),
                                                total=len(live_tools) or None,
                                                message=(
                                                    f"{'完成' if tr.ok else '失敗'}：{tr.display_name or tr.name}"
                                                ),
                                            ) + "\n"

                                    tools_used_meta = [
                                        {
                                            "name": r.name,
                                            "display_name": r.display_name,
                                            "icon": r.icon,
                                            "ok": r.ok,
                                            "duration_ms": r.duration_ms,
                                            "arguments": r.arguments,
                                            "error": r.error,
                                            "error_code": r.error_code,
                                        }
                                        for r in tool_results
                                    ]
                                    yield _tool_event_payload(
                                        "done",
                                        tools=live_tools,
                                        step=len(tool_results),
                                        total=len(tool_results),
                                        message="工具階段完成，正在產生回覆…",
                                    ) + "\n"
                                else:
                                    yield _tool_event_payload(
                                        "skipped",
                                        message="本次無需使用工具",
                                        tools=[],
                                    ) + "\n"
                        except Exception as e:
                            logger.warning(f"⚠️ [Streaming] Tool 階段失敗，改直接串流: {e}")
                            yield _tool_event_payload(
                                "error",
                                message=f"工具階段發生問題，改為直接回答（{type(e).__name__}）",
                                tools=[],
                            ) + "\n"
                            final_messages = messages

                    # 真實 OpenAI stream=True：逐 token 推給前端
                    async for event in generate_response_stream(
                        final_messages,
                        model=selected_model,
                        temperature=selected_temperature,
                        max_tokens=stream_max_tokens,
                    ):
                        if not isinstance(event, dict):
                            # 相容舊字串
                            full_response += str(event)
                            yield str(event)
                            continue
                        if event.get("type") == "content":
                            text = event.get("text") or ""
                            full_response += text
                            yield text
                        elif event.get("type") == "usage":
                            stream_usage = event.get("usage")
                except Exception as e:
                    err = f"[ERROR] Streaming 失敗: {e}"
                    logger.error(err, exc_info=True)
                    full_response = err
                    yield err
                finally:
                    # 合併 tool + stream usage 並記錄
                    merged = _merge_usage(tool_usage, stream_usage)
                    usage_payload = None
                    try:
                        if merged["total_tokens"] > 0 or merged["prompt_tokens"] > 0:
                            usage_payload = _record_usage(
                                user_id=request.user_id,
                                conversation_id=request.conversation_id,
                                model=selected_model,
                                usage=merged,
                                endpoint="chat_stream",
                                meta={"stream": True, "use_tools": use_tools},
                            )
                        else:
                            # 無 API usage 時仍回傳空用量摘要
                            summary = tracker.get_user_daily_summary(request.user_id)
                            usage_payload = {
                                "prompt_tokens": 0,
                                "completion_tokens": 0,
                                "total_tokens": 0,
                                "cost_usd": 0,
                                "model": selected_model,
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
                    except Exception as e:
                        logger.warning(f"⚠️ 記錄 streaming token 失敗: {e}")

                    speech_text = None
                    if request.voice_mode or request.car_mode or request.speak_response:
                        try:
                            from backend.voice_router import sanitize_for_speech

                            speech_text, _ = sanitize_for_speech(
                                full_response, strip_emojis=True, max_chars=800
                            )
                        except Exception:
                            speech_text = full_response

                    meta = {
                        "blocked": False,
                        "usage": usage_payload,
                        "tools_used": tools_used_meta,
                        "speech_text": speech_text,
                        "voice_mode": request.voice_mode,
                        "car_mode": request.car_mode,
                    }
                    try:
                        yield USAGE_META_PREFIX + json.dumps(meta, ensure_ascii=False)
                    except Exception:
                        pass

                    asyncio.create_task(_post_stream_tasks(full_response))
                    logger.info(
                        f"✅ Streaming 完成，已排程背景任務（長度: {len(full_response)} 字）"
                    )

            return StreamingResponse(
                stream_generator(),
                media_type="text/plain; charset=utf-8",
                headers={
                    "Cache-Control": "no-cache, no-transform",
                    "X-Accel-Buffering": "no",
                    "Connection": "keep-alive",
                },
            )

        # =========================================================
        # ✅ 原本的非 streaming 模式（含 Tool Calling + 完整錯誤處理）
        # =========================================================
        assistant_message = None
        collected_usages = []
        tools_used = []

        try:
            registry = get_tool_registry()
            tool_defs = get_openai_tool_definitions() if use_tools else []
            if not tool_defs:
                raise ValueError("tools_disabled")

            # 第一輪：讓 AI 決定要不要用工具
            tool_response = await generate_response_with_tools(
                messages,
                tools=tool_defs,
                model=selected_model,
                temperature=selected_temperature,
                max_tokens=1000
            )
            if tool_response.get("usage"):
                collected_usages.append(tool_response["usage"])

            if tool_response["finish_reason"] == "error":
                # Tool calling 呼叫本身失敗，降級為普通模式
                logger.warning(f"⚠️ Tool calling 呼叫失敗（{tool_response.get('error', '未知')}），降級為普通模式")
                raise ValueError("tool_calling_failed")

            # AI 決定呼叫工具
            if tool_response["finish_reason"] == "tool_calls" and tool_response["tool_calls"]:
                logger.info(f"🔧 AI 決定呼叫工具，數量：{len(tool_response['tool_calls'])}")

                # 把 AI 的 tool_calls 訊息加進對話
                messages.append(tool_response["raw_message"])

                tool_results = await registry.execute_openai_tool_calls(
                    tool_response["tool_calls"],
                    context={"user_id": request.user_id},
                )
                for tr in tool_results:
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tr.tool_call_id,
                            "content": tr.content,
                        }
                    )
                    tools_used.append(
                        {
                            "name": tr.name,
                            "display_name": tr.display_name,
                            "icon": tr.icon,
                            "ok": tr.ok,
                            "duration_ms": tr.duration_ms,
                            "arguments": tr.arguments,
                            "error": tr.error,
                            "error_code": tr.error_code,
                        }
                    )
                    logger.info(
                        f"{'✅' if tr.ok else '⚠️'} 工具 {tr.name} 完成 "
                        f"id={tr.tool_call_id} ok={tr.ok} {tr.duration_ms}ms"
                    )

                # 第二輪：讓 AI 根據工具結果生成最終回答
                final_result = await generate_response(
                    openai_client,
                    messages,
                    model=selected_model,
                    max_tokens=voice_max_tokens if request.voice_mode or request.car_mode else 1000,
                    temperature=selected_temperature,
                    return_usage=True,
                )
                assistant_message = final_result["content"]
                collected_usages.append(final_result.get("usage"))
            else:
                # AI 不需要工具，直接用第一輪的回答
                assistant_message = tool_response["content"]
                if not assistant_message:
                    raise ValueError("empty_first_response")

        except Exception as tool_err:
            # 任何工具流程失敗，降級為不帶工具的普通呼叫
            logger.warning(f"⚠️ Tool calling 流程失敗（{tool_err}），降級為普通 generate_response")
            final_result = await generate_response(
                openai_client,
                messages,
                model=selected_model,
                max_tokens=voice_max_tokens if request.voice_mode or request.car_mode else 1000,
                temperature=selected_temperature,
                return_usage=True,
            )
            assistant_message = final_result["content"]
            collected_usages.append(final_result.get("usage"))

        # 輸出端審核（可選，預設開啟）
        if os.getenv("MODERATION_CHECK_OUTPUT", "true").lower() not in ("0", "false", "no"):
            out_mod = await moderate_text(assistant_message or "", client=openai_client)
            if out_mod.get("blocked"):
                assistant_message = (
                    "抱歉，這次回覆未通過內容安全審核，我換個溫柔的方式陪你聊好嗎？✨"
                )

        merged_usage = _merge_usage(*collected_usages)
        usage_payload = _record_usage(
            user_id=request.user_id,
            conversation_id=request.conversation_id,
            model=selected_model,
            usage=merged_usage,
            endpoint="chat",
            meta={
                "stream": False,
                "use_tools": use_tools,
                "voice_mode": request.voice_mode,
                "car_mode": request.car_mode,
            },
        )

        # 3. [重要] 保持核心記憶立即儲存 (確保主訊息不會丟失)
        await memory_system.save_memory(
            request.conversation_id,
            request.user_message,
            assistant_message,
            emotion_analysis,
            ai_id=request.ai_id,
            user_id=request.user_id,
        )

        background_tasks.add_task(
            run_post_chat_tasks,
            request, 
            assistant_message, 
            emotion_analysis
        )

        speech_text = None
        if request.voice_mode or request.car_mode or request.speak_response:
            try:
                from backend.voice_router import sanitize_for_speech

                speech_text, _ = sanitize_for_speech(
                    assistant_message or "", strip_emojis=True, max_chars=800
                )
            except Exception:
                speech_text = assistant_message

        return ChatResponse(
            assistant_message=assistant_message,
            emotion_analysis=emotion_analysis,
            conversation_id=request.conversation_id,
            reflection=None,
            speech_text=speech_text,
            usage=usage_payload,
            usage_summary=usage_payload.get("daily"),
            tools_used=tools_used or None,
        )

    except HTTPException:
        # 預算超額、驗證失敗等預期 HTTP 錯誤不可被吞成 500
        raise
    except Exception as e:
        traceback_str = traceback.format_exc()
        logger.error(f"🔥 Chat Endpoint 發生嚴重錯誤: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="載體內部光流異常，請檢查日誌。")
