"""
Token Accounting (Infrastructure Phase).

- Counts prompt / completion / total tokens via tiktoken
- Estimates cost (delegates pricing table similar to token_tracker)
- Tokens are NOT written into message text; stored separately
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger("token_counter")

# USD per 1M tokens (aligned with token_tracker defaults)
_DEFAULT_PRICING = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "text-embedding-3-small": {"input": 0.02, "output": 0.0},
}


def _get_encoder(model: str = "gpt-4o-mini"):
    try:
        import tiktoken

        try:
            return tiktoken.encoding_for_model(model)
        except Exception:
            return tiktoken.get_encoding("cl100k_base")
    except Exception as e:
        logger.warning("tiktoken unavailable, fallback char estimator: %s", e)
        return None


def count_text_tokens(text: str, *, model: str = "gpt-4o-mini") -> int:
    text = text or ""
    enc = _get_encoder(model)
    if enc is None:
        # rough fallback ~4 chars/token
        return max(1, len(text) // 4) if text else 0
    try:
        return len(enc.encode(text))
    except Exception:
        return max(1, len(text) // 4) if text else 0


def count_messages_tokens(
    messages: List[Dict[str, Any]],
    *,
    model: str = "gpt-4o-mini",
) -> int:
    """OpenAI-style rough message token count."""
    total = 0
    for m in messages or []:
        total += 4  # role overhead approx
        content = m.get("content")
        if isinstance(content, str):
            total += count_text_tokens(content, model=model)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("text"):
                    total += count_text_tokens(str(part["text"]), model=model)
                else:
                    total += count_text_tokens(str(part), model=model)
        total += count_text_tokens(str(m.get("role") or ""), model=model)
    total += 2
    return total


def estimate_cost_usd(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> float:
    pricing = _DEFAULT_PRICING.get(model) or _DEFAULT_PRICING["gpt-4o-mini"]
    cost = (prompt_tokens / 1_000_000.0) * pricing["input"] + (
        completion_tokens / 1_000_000.0
    ) * pricing["output"]
    return round(cost, 8)


def build_usage_record(
    *,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: Optional[int] = None,
    model: str = "gpt-4o-mini",
    conversation_id: str = "",
    user_id: str = "",
    source: str = "chat",
) -> Dict[str, Any]:
    p = int(prompt_tokens or 0)
    c = int(completion_tokens or 0)
    t = int(total_tokens if total_tokens is not None else (p + c))
    return {
        "prompt_tokens": p,
        "completion_tokens": c,
        "total_tokens": t,
        "estimated_cost": estimate_cost_usd(model, p, c),
        "model": model,
        "conversation_id": conversation_id,
        "user_id": user_id,
        "source": source,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def account_turn(
    *,
    user_message: str,
    assistant_message: str,
    model: str = "gpt-4o-mini",
    system_prompt: str = "",
    conversation_id: str = "",
    user_id: str = "",
    usage_from_api: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Prefer API usage if provided; otherwise estimate with tiktoken.
    Does NOT embed tokens into message text.
    """
    if usage_from_api:
        p = int(usage_from_api.get("prompt_tokens") or 0)
        c = int(usage_from_api.get("completion_tokens") or 0)
        t = int(usage_from_api.get("total_tokens") or (p + c))
        rec = build_usage_record(
            prompt_tokens=p,
            completion_tokens=c,
            total_tokens=t,
            model=model,
            conversation_id=conversation_id,
            user_id=user_id,
            source="api_usage",
        )
        rec["token_ids"] = {
            "user": None,
            "assistant": None,
            "note": "API usage preferred; raw token ids not stored in message",
        }
        return rec

    prompt_blob = f"{system_prompt}\n{user_message}".strip()
    p = count_text_tokens(prompt_blob, model=model)
    c = count_text_tokens(assistant_message or "", model=model)
    rec = build_usage_record(
        prompt_tokens=p,
        completion_tokens=c,
        model=model,
        conversation_id=conversation_id,
        user_id=user_id,
        source="tiktoken_estimate",
    )
    # separate raw token id lists (not in message text)
    enc = _get_encoder(model)
    if enc is not None:
        try:
            rec["token_ids"] = {
                "user": enc.encode(user_message or "")[:512],
                "assistant": enc.encode(assistant_message or "")[:512],
            }
        except Exception:
            rec["token_ids"] = {"user": [], "assistant": []}
    else:
        rec["token_ids"] = {"user": [], "assistant": []}
    return rec


def append_token_ledger(
    record: Dict[str, Any],
    *,
    path: Optional[Union[str, Path]] = None,
) -> Path:
    """
    Persist token accounting separately from message bodies (JSONL ledger).
    """
    default = Path(__file__).resolve().parents[2] / "data" / "token_ledger.jsonl"
    out = Path(path or os.getenv("TOKEN_LEDGER_PATH", str(default)))
    out.parent.mkdir(parents=True, exist_ok=True)
    # strip large token_ids for ledger size if needed — keep short
    row = dict(record)
    tids = row.get("token_ids") or {}
    if isinstance(tids, dict):
        row["token_ids"] = {
            k: (v[:64] if isinstance(v, list) else v) for k, v in tids.items()
        }
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return out
