"""
對話歷史管理 API

- 列出 / 搜尋對話
- AI 總結對話
- 刪除特定對話
"""
from __future__ import annotations

import os
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.supabase_handler import get_supabase
from backend.openai_handler import get_openai_client
from backend.redis_interface import RedisInterface

router = APIRouter()
logger = logging.getLogger("history_router")

redis_interface = RedisInterface()


def _memories_table() -> str:
    return os.getenv("SUPABASE_MEMORIES_TABLE", "xiaochenguang_memories")


def _supabase():
    return get_supabase()


class ConversationSummaryItem(BaseModel):
    conversation_id: str
    user_id: Optional[str] = None
    message_count: int = 0
    first_at: Optional[str] = None
    last_at: Optional[str] = None
    preview: str = ""
    title: str = ""


class SearchHit(BaseModel):
    conversation_id: str
    user_message: str = ""
    assistant_message: str = ""
    created_at: Optional[str] = None
    snippet: str = ""


class SummarizeRequest(BaseModel):
    conversation_id: str
    user_id: str = "default_user"
    max_messages: int = Field(default=40, ge=5, le=100)
    language: str = "zh-TW"


class DeleteResponse(BaseModel):
    success: bool
    conversation_id: str
    deleted_count: int = 0
    redis_cleared: bool = False
    message: str = ""


def _preview_text(user_msg: str, asst_msg: str, limit: int = 80) -> str:
    text = (user_msg or asst_msg or "").strip().replace("\n", " ")
    if len(text) > limit:
        return text[:limit] + "…"
    return text or "（無內容）"


def _title_from_first(user_msg: str) -> str:
    t = (user_msg or "").strip().replace("\n", " ")
    if not t:
        return "未命名對話"
    return (t[:28] + "…") if len(t) > 28 else t


@router.get("/history/conversations")
async def list_conversations(
    user_id: str = Query(..., description="使用者 ID"),
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """列出使用者的對話串（依最後活動時間排序）。"""
    try:
        table = _memories_table()
        # 抓取足夠筆數後在記憶體聚合（Supabase 無 group by 時的穩健做法）
        fetch_limit = min(2000, max(200, (offset + limit) * 40))
        result = (
            _supabase()
            .table(table)
            .select("conversation_id, user_id, user_message, assistant_message, created_at")
            .eq("user_id", user_id)
            .eq("memory_type", "conversation")
            .order("created_at", desc=True)
            .limit(fetch_limit)
            .execute()
        )
        rows = result.data or []
        buckets: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            cid = row.get("conversation_id") or ""
            if not cid:
                continue
            b = buckets.get(cid)
            created = row.get("created_at") or ""
            if not b:
                buckets[cid] = {
                    "conversation_id": cid,
                    "user_id": row.get("user_id") or user_id,
                    "message_count": 1,
                    "first_at": created,
                    "last_at": created,
                    "preview": _preview_text(
                        row.get("user_message") or "",
                        row.get("assistant_message") or "",
                    ),
                    "title": "",
                    "_first_user": row.get("user_message") or "",
                }
            else:
                b["message_count"] += 1
                # 因 desc 排序，先到的是最新
                if created and (not b["last_at"] or created > b["last_at"]):
                    b["last_at"] = created
                    b["preview"] = _preview_text(
                        row.get("user_message") or "",
                        row.get("assistant_message") or "",
                    )
                if created and (not b["first_at"] or created < b["first_at"]):
                    b["first_at"] = created
                    b["_first_user"] = row.get("user_message") or b.get("_first_user") or ""

        items = list(buckets.values())
        for it in items:
            it["title"] = _title_from_first(it.pop("_first_user", "") or it.get("preview", ""))
        items.sort(key=lambda x: x.get("last_at") or "", reverse=True)
        total = len(items)
        page = items[offset : offset + limit]
        return {
            "user_id": user_id,
            "total": total,
            "limit": limit,
            "offset": offset,
            "conversations": page,
        }
    except Exception as e:
        logger.exception("❌ 列出對話失敗")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/conversations/{conversation_id}")
async def get_conversation_detail(
    conversation_id: str,
    user_id: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=300),
):
    """取得單一對話完整訊息。"""
    try:
        table = _memories_table()
        q = (
            _supabase()
            .table(table)
            .select(
                "id, conversation_id, user_id, user_message, assistant_message, created_at, importance_score"
            )
            .eq("conversation_id", conversation_id)
            .eq("memory_type", "conversation")
            .order("created_at", desc=False)
            .limit(limit)
        )
        if user_id:
            q = q.eq("user_id", user_id)
        result = q.execute()
        rows = result.data or []
        messages = []
        for row in rows:
            ts = (row.get("created_at") or "")[:19].replace("T", " ")
            if row.get("user_message"):
                messages.append(
                    {
                        "id": row.get("id"),
                        "type": "user",
                        "content": row["user_message"],
                        "timestamp": ts,
                    }
                )
            if row.get("assistant_message"):
                messages.append(
                    {
                        "id": row.get("id"),
                        "type": "assistant",
                        "content": row["assistant_message"],
                        "timestamp": ts,
                    }
                )
        return {
            "conversation_id": conversation_id,
            "user_id": user_id or (rows[0].get("user_id") if rows else None),
            "message_count": len(rows),
            "messages": messages,
            "raw_count": len(rows),
        }
    except Exception as e:
        logger.exception("❌ 讀取對話詳情失敗")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/search")
async def search_history(
    user_id: str = Query(...),
    q: str = Query(..., min_length=1, description="搜尋關鍵字"),
    limit: int = Query(default=30, ge=1, le=100),
):
    """搜尋歷史對話（使用者訊息 / 助理訊息）。"""
    query = (q or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="搜尋關鍵字不可為空")

    try:
        table = _memories_table()
        # PostgREST or 過濾：user_message / assistant_message ilike
        # 使用兩次查詢合併，相容性較好
        sb = _supabase()
        pattern = f"%{query}%"

        def _run(column: str):
            return (
                sb.table(table)
                .select(
                    "conversation_id, user_message, assistant_message, created_at"
                )
                .eq("user_id", user_id)
                .eq("memory_type", "conversation")
                .ilike(column, pattern)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )

        hits_map: Dict[str, Dict[str, Any]] = {}
        for col in ("user_message", "assistant_message"):
            try:
                res = _run(col)
                for row in res.data or []:
                    key = f"{row.get('conversation_id')}|{row.get('created_at')}|{col}"
                    um = row.get("user_message") or ""
                    am = row.get("assistant_message") or ""
                    snippet_src = um if col == "user_message" else am
                    idx = snippet_src.lower().find(query.lower())
                    if idx >= 0:
                        start = max(0, idx - 20)
                        end = min(len(snippet_src), idx + len(query) + 40)
                        snippet = ("…" if start > 0 else "") + snippet_src[start:end] + (
                            "…" if end < len(snippet_src) else ""
                        )
                    else:
                        snippet = (snippet_src or "")[:60]
                    hits_map[key] = {
                        "conversation_id": row.get("conversation_id"),
                        "user_message": um,
                        "assistant_message": am,
                        "created_at": row.get("created_at"),
                        "snippet": snippet,
                        "matched_field": col,
                    }
            except Exception as e:
                logger.warning(f"⚠️ 搜尋欄位 {col} 失敗: {e}")

        hits = list(hits_map.values())
        hits.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        hits = hits[:limit]

        # 也回傳涉及的 conversation 聚合
        conv_ids = []
        seen = set()
        for h in hits:
            cid = h.get("conversation_id")
            if cid and cid not in seen:
                seen.add(cid)
                conv_ids.append(cid)

        return {
            "user_id": user_id,
            "query": query,
            "total_hits": len(hits),
            "hits": hits,
            "conversation_ids": conv_ids,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("❌ 搜尋歷史失敗")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/history/summarize")
async def summarize_conversation(request: SummarizeRequest):
    """AI 總結指定對話。"""
    try:
        table = _memories_table()
        q = (
            _supabase()
            .table(table)
            .select("user_message, assistant_message, created_at")
            .eq("conversation_id", request.conversation_id)
            .eq("memory_type", "conversation")
            .order("created_at", desc=False)
            .limit(request.max_messages)
        )
        if request.user_id and request.user_id != "default_user":
            q = q.eq("user_id", request.user_id)
        result = q.execute()
        rows = result.data or []
        if not rows:
            raise HTTPException(status_code=404, detail="找不到此對話或沒有訊息")

        lines = []
        for row in rows:
            if row.get("user_message"):
                lines.append(f"使用者：{row['user_message'][:500]}")
            if row.get("assistant_message"):
                lines.append(f"小宸光：{row['assistant_message'][:500]}")
        transcript = "\n".join(lines)
        if len(transcript) > 12000:
            transcript = transcript[:12000] + "\n…(截斷)"

        client = get_openai_client()
        model = os.getenv("HISTORY_SUMMARY_MODEL", "gpt-4o-mini")
        prompt = f"""請用繁體中文總結以下對話，輸出結構化重點：

1. **一句話摘要**
2. **主要話題**（條列 2-5 點）
3. **使用者情緒 / 需求**
4. **重要結論或待辦**（若有）
5. **可延續的話題建議**

對話內容：
{transcript}
"""
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "你是對話整理助手，擅長溫暖、清楚的繁中摘要。",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=800,
            temperature=0.4,
        )
        summary = (response.choices[0].message.content or "").strip()
        usage = getattr(response, "usage", None)
        usage_dict = {
            "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
            "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
            "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
        }

        # 可選：把摘要寫回 memories（memory_type=summary）
        saved = False
        try:
            _supabase().table(table).insert(
                {
                    "conversation_id": request.conversation_id,
                    "user_id": request.user_id,
                    "memory_type": "conversation_summary",
                    "user_message": "對話總結請求",
                    "assistant_message": summary,
                    "document_content": summary,
                    "created_at": datetime.utcnow().isoformat(),
                    "platform": "Web",
                }
            ).execute()
            saved = True
        except Exception as e:
            logger.warning(f"⚠️ 摘要寫入 Supabase 失敗（不影響回傳）: {e}")

        try:
            from backend.token_tracker import get_token_tracker

            get_token_tracker().record(
                user_id=request.user_id,
                conversation_id=request.conversation_id,
                model=model,
                prompt_tokens=usage_dict["prompt_tokens"],
                completion_tokens=usage_dict["completion_tokens"],
                total_tokens=usage_dict["total_tokens"],
                endpoint="history_summarize",
            )
        except Exception:
            pass

        return {
            "conversation_id": request.conversation_id,
            "summary": summary,
            "message_count": len(rows),
            "model": model,
            "usage": usage_dict,
            "saved": saved,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("❌ 總結對話失敗")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/history/conversations/{conversation_id}", response_model=DeleteResponse)
async def delete_conversation(
    conversation_id: str,
    user_id: str = Query(..., description="必須提供，避免誤刪他人對話"),
    hard: bool = Query(default=True, description="是否永久刪除"),
):
    """刪除特定對話（該 user 下的 conversation 記憶）。"""
    if not conversation_id or not user_id:
        raise HTTPException(status_code=400, detail="缺少 conversation_id 或 user_id")

    try:
        table = _memories_table()
        # 先計數
        existing = (
            _supabase()
            .table(table)
            .select("id")
            .eq("conversation_id", conversation_id)
            .eq("user_id", user_id)
            .execute()
        )
        count = len(existing.data or [])
        if count == 0:
            # 也嘗試只靠 conversation_id（訪客 id 不一致時）
            existing2 = (
                _supabase()
                .table(table)
                .select("id")
                .eq("conversation_id", conversation_id)
                .limit(5)
                .execute()
            )
            if not existing2.data:
                raise HTTPException(status_code=404, detail="找不到此對話")

        if hard:
            (
                _supabase()
                .table(table)
                .delete()
                .eq("conversation_id", conversation_id)
                .eq("user_id", user_id)
                .execute()
            )
            # 一併刪 summary 類型
            try:
                (
                    _supabase()
                    .table(table)
                    .delete()
                    .eq("conversation_id", conversation_id)
                    .eq("user_id", user_id)
                    .eq("memory_type", "conversation_summary")
                    .execute()
                )
            except Exception:
                pass
        deleted_count = count

        redis_cleared = False
        try:
            if redis_interface.redis:
                # 清除短期對話與上傳暫存
                redis_interface.clear_conversation(conversation_id)
                keys = redis_interface.redis.keys(f"upload:{conversation_id}:*")
                if keys:
                    redis_interface.redis.delete(*keys)
                redis_cleared = True
        except Exception as e:
            logger.warning(f"⚠️ Redis 清除失敗: {e}")

        logger.info(
            f"🗑️ 已刪除對話 conv={conversation_id[:12]}... user={user_id[:8]}... n={deleted_count}"
        )
        return DeleteResponse(
            success=True,
            conversation_id=conversation_id,
            deleted_count=deleted_count,
            redis_cleared=redis_cleared,
            message=f"已刪除 {deleted_count} 筆記憶紀錄",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("❌ 刪除對話失敗")
        raise HTTPException(status_code=500, detail=str(e))
