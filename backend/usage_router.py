"""Token 使用量查詢 API"""
from fastapi import APIRouter, Query
from typing import Optional
import logging

from backend.token_tracker import get_token_tracker

router = APIRouter()
logger = logging.getLogger("usage_router")


@router.get("/usage/summary")
async def usage_summary(user_id: Optional[str] = Query(default=None)):
    """今日用量摘要（可帶 user_id）。"""
    tracker = get_token_tracker()
    global_sum = tracker.get_global_daily_summary()
    result = {
        "global": {
            "day": global_sum["day"],
            "calls": global_sum["calls"],
            "prompt_tokens": global_sum["prompt_tokens"],
            "completion_tokens": global_sum["completion_tokens"],
            "total_tokens": global_sum["total_tokens"],
            "cost_usd": global_sum["cost_usd"],
            "budget_usd": global_sum["budget_usd"],
            "remaining_usd": global_sum["remaining_usd"],
            "budget_exceeded": global_sum["budget_exceeded"],
        }
    }
    if user_id:
        user_sum = tracker.get_user_daily_summary(user_id)
        result["user"] = {
            "user_id": user_sum["user_id"],
            "day": user_sum["day"],
            "calls": user_sum["calls"],
            "prompt_tokens": user_sum["prompt_tokens"],
            "completion_tokens": user_sum["completion_tokens"],
            "total_tokens": user_sum["total_tokens"],
            "cost_usd": user_sum["cost_usd"],
            "budget_usd": user_sum["budget_usd"],
            "remaining_usd": user_sum["remaining_usd"],
            "budget_exceeded": user_sum["budget_exceeded"],
            "recent": [
                {
                    "ts": r.get("ts"),
                    "model": r.get("model"),
                    "prompt_tokens": r.get("prompt_tokens"),
                    "completion_tokens": r.get("completion_tokens"),
                    "total_tokens": r.get("total_tokens"),
                    "cost_usd": r.get("cost_usd"),
                    "endpoint": r.get("endpoint"),
                }
                for r in user_sum.get("recent", [])
            ],
        }
    return result


@router.get("/usage/user/{user_id}")
async def usage_user(user_id: str):
    """指定使用者今日用量。"""
    tracker = get_token_tracker()
    return tracker.get_user_daily_summary(user_id)
