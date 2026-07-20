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
from backend.tools import web_search, TOOL_DEFINITIONS
from backend.token_tracker import get_token_tracker, estimate_cost_usd
from backend.moderation import moderate_text, format_block_message

router = APIRouter()
logger = logging.getLogger("chat_router")
redis_interface = RedisInterface()

# 串流結尾附加用量 meta 的標記（前端可解析）
USAGE_META_PREFIX = "\n__XCG_META__"

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
    
class ChatResponse(BaseModel):
    assistant_message: str
    emotion_analysis: dict
    conversation_id: str
    reflection: Optional[dict] = None
    usage: Optional[dict] = None
    usage_summary: Optional[dict] = None


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

        # Retrieve file content from Redis
        file_content = ""
        try:
            if redis_interface.redis:
                keys = redis_interface.redis.keys(f"upload:{request.conversation_id}:*")
                if keys:
                    latest_key = keys[-1]
                    file_data_json = redis_interface.redis.get(latest_key)
                    if file_data_json:
                        file_data = json.loads(file_data_json)
                        file_content = file_data.get("content", "")
                        logger.info(f"📄 成功從 Redis 檢索檔案內容: {latest_key}")
        except Exception as e:
            logger.warning(f"⚠️ 從 Redis 檢索檔案內容失敗: {e}")

        messages, emotion_analysis = await prompt_engine.build_prompt(
            request.user_message,
            recalled_memories,
            conversation_history,
            file_content
        )

        # ✅ 根據 AI ID 選擇模型
        if request.ai_id == "story_master_v1":
            selected_model = "gpt-4o"
            selected_temperature = 0.95
            logger.info("✨ 啟用：Story Master 故事光光寶貝")
        else:
            selected_model = "gpt-4o-mini"
            selected_temperature = 0.8
            logger.info("🌟 啟用：Xiaochenguang 預設光光寶貝")

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

            async def _prepare_messages_with_optional_tools(base_messages: list):
                """可選 tool calling；完成後仍用 stream=True 輸出最終回答。回傳 (messages, tool_usage)"""
                if not use_tools:
                    return base_messages, None
                try:
                    tool_response = await generate_response_with_tools(
                        base_messages,
                        tools=TOOL_DEFINITIONS,
                        model=selected_model,
                        temperature=selected_temperature,
                        max_tokens=1000,
                    )
                    tool_usage = tool_response.get("usage")
                    if not (
                        tool_response.get("finish_reason") == "tool_calls"
                        and tool_response.get("tool_calls")
                    ):
                        # 不需工具：丟棄預檢全文，改走真正 OpenAI 串流
                        # 仍記錄 tool 預檢用量（若有）
                        return base_messages, tool_usage

                    logger.info(
                        f"🔧 [Streaming] 工具呼叫 x{len(tool_response['tool_calls'])}"
                    )
                    stream_messages = list(base_messages)
                    stream_messages.append(tool_response["raw_message"])

                    for tool_call in tool_response["tool_calls"]:
                        try:
                            fn_name = tool_call.function.name
                            fn_args = json.loads(tool_call.function.arguments)
                        except (AttributeError, json.JSONDecodeError) as e:
                            logger.warning(f"⚠️ [Streaming] 解析 tool_call 失敗: {e}")
                            stream_messages.append({
                                "role": "tool",
                                "tool_call_id": getattr(tool_call, "id", "unknown"),
                                "content": "[TOOL_PARSE_ERROR] 工具呼叫格式錯誤",
                            })
                            continue

                        tool_call_id = getattr(tool_call, "id", "unknown")
                        try:
                            if fn_name == "web_search":
                                tool_result = await web_search(query=fn_args.get("query", ""))
                            else:
                                tool_result = f"[UNKNOWN_TOOL] 不認識的工具：{fn_name}"
                        except Exception as e:
                            tool_result = "[TOOL_EXEC_ERROR] 工具執行失敗"
                            logger.warning(f"⚠️ [Streaming] 工具 {fn_name} 失敗: {e}")

                        stream_messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": tool_result,
                        })
                    return stream_messages, tool_usage
                except Exception as e:
                    logger.warning(f"⚠️ [Streaming] Tool 階段失敗，改直接串流: {e}")
                    return base_messages, None

            async def stream_generator():
                full_response = ""
                stream_usage = None
                tool_usage = None
                try:
                    final_messages, tool_usage = await _prepare_messages_with_optional_tools(messages)
                    # 真實 OpenAI stream=True：逐 token 推給前端
                    async for event in generate_response_stream(
                        final_messages,
                        model=selected_model,
                        temperature=selected_temperature,
                        max_tokens=2000,
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

                    meta = {
                        "blocked": False,
                        "usage": usage_payload,
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

        try:
            # 第一輪：讓 AI 決定要不要用工具
            tool_response = await generate_response_with_tools(
                messages,
                tools=TOOL_DEFINITIONS,
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

                # 執行每個工具並收集結果
                for tool_call in tool_response["tool_calls"]:
                    try:
                        fn_name = tool_call.function.name
                        fn_args = json.loads(tool_call.function.arguments)
                    except (AttributeError, json.JSONDecodeError) as e:
                        logger.warning(f"⚠️ 解析 tool_call 格式失敗: {e}")
                        messages.append({
                            "role": "tool",
                            "tool_call_id": getattr(tool_call, 'id', 'unknown'),
                            "content": "[TOOL_PARSE_ERROR] 工具呼叫格式錯誤"
                        })
                        continue

                    logger.info(f"🔧 執行工具：{fn_name}，tool_call_id={fn_name and tool_call.id}，參數：{fn_args}")
                    tool_result = ""

                    try:
                        if fn_name == "web_search":
                            tool_result = await web_search(query=fn_args.get("query", ""))
                        else:
                            tool_result = f"[UNKNOWN_TOOL] 不認識的工具：{fn_name}"
                            logger.warning(f"⚠️ 未知工具：{fn_name}")
                    except Exception as e:
                        tool_result = "[TOOL_EXEC_ERROR] 工具執行失敗"
                        logger.warning(f"⚠️ 工具 {fn_name} 執行異常，tool_call_id={tool_call.id}: {e}")

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_result
                    })
                    logger.info(f"✅ 工具 {fn_name} 完成，tool_call_id={tool_call.id}，結果長度：{len(tool_result)}")

                # 第二輪：讓 AI 根據工具結果生成最終回答
                final_result = await generate_response(
                    openai_client,
                    messages,
                    model=selected_model,
                    max_tokens=1000,
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
                max_tokens=1000,
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
            meta={"stream": False, "use_tools": use_tools},
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

        return ChatResponse(
            assistant_message=assistant_message,
            emotion_analysis=emotion_analysis,
            conversation_id=request.conversation_id,
            reflection=None,
            usage=usage_payload,
            usage_summary=usage_payload.get("daily"),
        )

    except Exception as e:
        traceback_str = traceback.format_exc()
        logger.error(f"🔥 Chat Endpoint 發生嚴重錯誤: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="載體內部光流異常，請檢查日誌。")
