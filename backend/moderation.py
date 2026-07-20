"""
內容安全審核（OpenAI Moderation API）

擋住不適當內容；失敗時採 fail-open 或 fail-closed 由環境變數控制。
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger("moderation")

# 這些分類被標為 true 時阻擋
DEFAULT_BLOCK_CATEGORIES = {
    "hate",
    "hate/threatening",
    "harassment",
    "harassment/threatening",
    "self-harm",
    "self-harm/intent",
    "self-harm/instructions",
    "sexual",
    "sexual/minors",
    "violence",
    "violence/graphic",
    "illicit",
    "illicit/violent",
}


def _parse_block_categories() -> set:
    raw = os.getenv("MODERATION_BLOCK_CATEGORIES", "")
    if not raw.strip():
        return set(DEFAULT_BLOCK_CATEGORIES)
    return {c.strip() for c in raw.split(",") if c.strip()}


async def moderate_text(
    text: str,
    *,
    client: Any = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    審核文字內容。

    回傳:
      {
        "flagged": bool,
        "blocked": bool,
        "categories": {name: bool},
        "category_scores": {name: float},
        "flagged_categories": [str],
        "model": str,
        "error": optional str,
      }
    """
    text = (text or "").strip()
    if not text:
        return {
            "flagged": False,
            "blocked": False,
            "categories": {},
            "category_scores": {},
            "flagged_categories": [],
            "model": model or "none",
        }

    # 可關閉審核
    if os.getenv("MODERATION_ENABLED", "true").lower() in ("0", "false", "no"):
        return {
            "flagged": False,
            "blocked": False,
            "categories": {},
            "category_scores": {},
            "flagged_categories": [],
            "model": "disabled",
        }

    fail_closed = os.getenv("MODERATION_FAIL_CLOSED", "false").lower() in (
        "1",
        "true",
        "yes",
    )
    model_name = model or os.getenv("MODERATION_MODEL", "omni-moderation-latest")
    block_cats = _parse_block_categories()

    try:
        if client is None:
            from backend.openai_handler import get_openai_client

            client = get_openai_client()

        # 同步 client 用 to_thread；若有 async 則直接 await
        import asyncio

        def _call():
            return client.moderations.create(model=model_name, input=text)

        if hasattr(client, "moderations") and asyncio.iscoroutinefunction(
            getattr(getattr(client, "moderations", None), "create", None)
        ):
            result = await client.moderations.create(model=model_name, input=text)
        else:
            result = await asyncio.to_thread(_call)

        item = result.results[0]
        categories_obj = getattr(item, "categories", None)
        scores_obj = getattr(item, "category_scores", None)

        categories: Dict[str, bool] = {}
        if categories_obj is not None:
            if hasattr(categories_obj, "model_dump"):
                categories = {
                    k: bool(v) for k, v in categories_obj.model_dump().items()
                }
            elif isinstance(categories_obj, dict):
                categories = {k: bool(v) for k, v in categories_obj.items()}
            else:
                # fallback: iterate known attrs
                for name in DEFAULT_BLOCK_CATEGORIES:
                    if hasattr(categories_obj, name.replace("/", "_")):
                        categories[name] = bool(
                            getattr(categories_obj, name.replace("/", "_"))
                        )
                # also try __dict__
                data = getattr(categories_obj, "__dict__", {}) or {}
                for k, v in data.items():
                    if not k.startswith("_"):
                        categories[k.replace("_", "/")] = bool(v)

        category_scores: Dict[str, float] = {}
        if scores_obj is not None:
            if hasattr(scores_obj, "model_dump"):
                category_scores = {
                    k: float(v) for k, v in scores_obj.model_dump().items()
                }
            elif isinstance(scores_obj, dict):
                category_scores = {k: float(v) for k, v in scores_obj.items()}

        flagged = bool(getattr(item, "flagged", False))
        flagged_categories = [k for k, v in categories.items() if v]
        # 僅在命中需阻擋分類時 blocked
        blocked = any(categories.get(c, False) for c in block_cats) or (
            flagged and not categories
        )

        out = {
            "flagged": flagged,
            "blocked": blocked,
            "categories": categories,
            "category_scores": category_scores,
            "flagged_categories": flagged_categories,
            "model": model_name,
        }
        if blocked:
            logger.warning(
                f"🚫 內容審核攔截 categories={flagged_categories}"
            )
        return out
    except Exception as e:
        logger.warning(f"⚠️ Moderation API 失敗: {e}")
        if fail_closed:
            return {
                "flagged": True,
                "blocked": True,
                "categories": {},
                "category_scores": {},
                "flagged_categories": ["moderation_error"],
                "model": model_name,
                "error": str(e),
            }
        return {
            "flagged": False,
            "blocked": False,
            "categories": {},
            "category_scores": {},
            "flagged_categories": [],
            "model": model_name,
            "error": str(e),
        }


def format_block_message(moderation: Dict[str, Any]) -> str:
    cats = moderation.get("flagged_categories") or []
    if cats:
        return (
            "⚠️ 內容未通過安全審核，已阻擋本次訊息。"
            f"（分類：{', '.join(cats[:5])}）請換個方式表達～"
        )
    return "⚠️ 內容未通過安全審核，已阻擋本次訊息。請換個方式表達～"
