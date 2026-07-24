"""
Chat side-services extracted from chat_router (Infrastructure Phase).

chat_router should orchestrate request/response; heavy memory/reflection/token
helpers live here without changing public API contracts.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger("chat_services")


def build_memory_backend(supabase, openai_client, memories_table: str, redis_interface=None):
    """Strangler factory — same behavior as chat_router._build_memory_system."""
    from modules.memory_system import MemorySystem

    try:
        from backend.modules.memory_manager import memory_v2_enabled, MemoryManager

        if memory_v2_enabled():
            v1 = MemorySystem(
                supabase,
                openai_client,
                memories_table,
                redis_interface=redis_interface,
            )
            return MemoryManager(v1).as_legacy()
    except Exception as e:
        logger.warning("Memory V2 factory failed, fallback V1: %s", e)
    return MemorySystem(
        supabase, openai_client, memories_table, redis_interface=redis_interface
    )


def normalize_reflection_for_storage(reflection: Any) -> Optional[Dict[str, Any]]:
    if reflection is None:
        return None
    try:
        from backend.modules.reflection_contract import normalize_reflection

        return normalize_reflection(reflection)
    except Exception:
        return reflection if isinstance(reflection, dict) else None


def account_and_ledger_tokens(
    *,
    user_message: str,
    assistant_message: str,
    model: str,
    conversation_id: str,
    user_id: str,
    usage_from_api: Optional[Dict[str, Any]] = None,
    write_ledger: bool = True,
) -> Dict[str, Any]:
    """Token accounting separated from message text."""
    try:
        from backend.modules.token_counter import account_turn, append_token_ledger

        rec = account_turn(
            user_message=user_message,
            assistant_message=assistant_message,
            model=model,
            conversation_id=conversation_id,
            user_id=user_id,
            usage_from_api=usage_from_api,
        )
        if write_ledger and os.getenv("TOKEN_LEDGER_ENABLED", "true").lower() not in (
            "0",
            "false",
            "no",
        ):
            append_token_ledger(rec)
        return rec
    except Exception as e:
        logger.warning("token account failed: %s", e)
        return usage_from_api or {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "estimated_cost": 0.0,
        }
