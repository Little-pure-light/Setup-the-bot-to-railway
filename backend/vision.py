"""
圖片理解（Vision）模組

- GPT-4o / GPT-4o-mini Vision
- 圖片安全檢查（大小、magic bytes、Moderation）
- 可回傳 token 用量供追蹤
"""
from __future__ import annotations

import base64
import logging
import os
import struct
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("vision")

# 預設：優先用 mini 控制成本；可用 VISION_MODEL 覆寫
DEFAULT_VISION_MODEL = os.getenv("VISION_MODEL", "gpt-4o-mini")
MAX_IMAGE_BYTES = int(os.getenv("MAX_IMAGE_BYTES", str(8 * 1024 * 1024)))  # 8MB
ALLOWED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
ALLOWED_MIME = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "image/gif",
}


class VisionSafetyError(Exception):
    """圖片未通過安全檢查"""

    def __init__(self, message: str, code: str = "unsafe_image"):
        super().__init__(message)
        self.code = code
        self.message = message


def _sniff_image(file_bytes: bytes) -> Tuple[Optional[str], Optional[str]]:
    """
    依 magic bytes 判斷圖片類型。
    回傳 (ext, mime) 或 (None, None)
    """
    if not file_bytes or len(file_bytes) < 12:
        return None, None

    # PNG
    if file_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png", "image/png"
    # JPEG
    if file_bytes[:3] == b"\xff\xd8\xff":
        return ".jpg", "image/jpeg"
    # GIF
    if file_bytes[:6] in (b"GIF87a", b"GIF89a"):
        return ".gif", "image/gif"
    # WEBP (RIFF....WEBP)
    if file_bytes[:4] == b"RIFF" and file_bytes[8:12] == b"WEBP":
        return ".webp", "image/webp"
    return None, None


def validate_image_bytes(
    file_bytes: bytes,
    filename: str = "",
    content_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    安全檢查圖片。通過時回傳 {ext, mime, size}；否則 raise VisionSafetyError。
    """
    if not file_bytes:
        raise VisionSafetyError("空檔案", "empty_file")

    size = len(file_bytes)
    if size > MAX_IMAGE_BYTES:
        raise VisionSafetyError(
            f"圖片過大（{size} bytes），上限 {MAX_IMAGE_BYTES} bytes",
            "too_large",
        )

    # 擋常見可執行檔 / 腳本開頭
    head = file_bytes[:64].lower()
    for bad in (b"<?php", b"<script", b"mz", b"\x7felf"):
        if head.startswith(bad) or bad in file_bytes[:16].lower():
            # MZ is windows PE — check start only
            if bad == b"mz" and not file_bytes[:2] in (b"MZ", b"mz"):
                continue
            if bad in (b"<?php", b"<script") and bad in head:
                raise VisionSafetyError("檔案內容疑似非圖片", "suspicious_content")
            if file_bytes[:2] == b"MZ":
                raise VisionSafetyError("檔案內容疑似非圖片", "suspicious_content")

    sniffed_ext, sniffed_mime = _sniff_image(file_bytes)
    if not sniffed_ext:
        raise VisionSafetyError("無法辨識為安全的圖片格式（僅支援 PNG/JPEG/WEBP/GIF）", "invalid_format")

    name_ext = os.path.splitext((filename or "").lower())[1]
    if name_ext and name_ext not in ALLOWED_IMAGE_EXTS:
        raise VisionSafetyError(f"副檔名不允許：{name_ext}", "invalid_extension")

    # 副檔名與內容不一致時以 sniff 為準，但若副檔名明顯衝突則擋
    if name_ext in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        if name_ext == ".jpeg":
            name_ext = ".jpg"
        sniff_norm = sniffed_ext
        if name_ext != sniff_norm and not (
            name_ext in (".jpg", ".jpeg") and sniff_norm == ".jpg"
        ):
            # jpeg/png 不一致
            if {name_ext, sniff_norm} != {".jpg", ".jpeg"}:
                logger.warning(
                    f"⚠️ 副檔名與內容不符 name={name_ext} sniff={sniffed_ext}"
                )
                # 仍允許但使用 sniff（許多相機會標錯）；嚴格模式可擋
                if os.getenv("VISION_STRICT_EXT", "false").lower() in ("1", "true", "yes"):
                    raise VisionSafetyError(
                        "副檔名與圖片內容不符",
                        "ext_mismatch",
                    )

    if content_type and content_type.split(";")[0].strip().lower() not in ALLOWED_MIME | {
        "application/octet-stream",
        "",
    }:
        # 允許瀏覽器送 octet-stream
        if content_type.split(";")[0].strip().lower() not in ALLOWED_MIME:
            if content_type not in ("application/octet-stream",):
                logger.warning(f"⚠️ 可疑 Content-Type: {content_type}")

    return {
        "ext": sniffed_ext,
        "mime": sniffed_mime,
        "size": size,
        "filename": filename or f"image{sniffed_ext}",
    }


async def moderate_image(
    file_bytes: bytes,
    mime: str,
    client: Any = None,
) -> Dict[str, Any]:
    """
    使用 OpenAI omni-moderation 檢查圖片。
    失敗時預設 fail-open（除非 MODERATION_FAIL_CLOSED=true）。
    """
    if os.getenv("VISION_MODERATION_ENABLED", "true").lower() in ("0", "false", "no"):
        return {"blocked": False, "flagged": False, "skipped": True}

    fail_closed = os.getenv("MODERATION_FAIL_CLOSED", "false").lower() in (
        "1",
        "true",
        "yes",
    )
    try:
        if client is None:
            from backend.openai_handler import get_openai_client

            client = get_openai_client()

        b64 = base64.b64encode(file_bytes).decode("utf-8")
        data_url = f"data:{mime};base64,{b64}"
        model = os.getenv("VISION_MODERATION_MODEL", "omni-moderation-latest")

        import asyncio

        def _call():
            return client.moderations.create(
                model=model,
                input=[
                    {
                        "type": "image_url",
                        "image_url": {"url": data_url},
                    }
                ],
            )

        result = await asyncio.to_thread(_call)
        item = result.results[0]
        flagged = bool(getattr(item, "flagged", False))
        categories = {}
        cat_obj = getattr(item, "categories", None)
        if cat_obj is not None:
            if hasattr(cat_obj, "model_dump"):
                categories = {k: bool(v) for k, v in cat_obj.model_dump().items()}
            elif isinstance(cat_obj, dict):
                categories = {k: bool(v) for k, v in cat_obj.items()}
        flagged_categories = [k for k, v in categories.items() if v]
        blocked = flagged or any(categories.values())
        if blocked:
            logger.warning(f"🚫 圖片審核攔截 categories={flagged_categories}")
        return {
            "blocked": blocked,
            "flagged": flagged,
            "flagged_categories": flagged_categories,
            "categories": categories,
            "model": model,
        }
    except Exception as e:
        logger.warning(f"⚠️ 圖片 Moderation 失敗: {e}")
        if fail_closed:
            return {
                "blocked": True,
                "flagged": True,
                "flagged_categories": ["moderation_error"],
                "error": str(e),
            }
        return {"blocked": False, "flagged": False, "error": str(e)}


def make_preview_data_url(
    file_bytes: bytes,
    mime: str,
    max_preview_bytes: int = 150_000,
) -> Optional[str]:
    """
    產生可給前端顯示的 data URL（僅小圖；過大則回 None，改用 file_url）。
    """
    if len(file_bytes) > max_preview_bytes:
        return None
    b64 = base64.b64encode(file_bytes).decode("utf-8")
    return f"data:{mime};base64,{b64}"


async def analyze_image(
    file_bytes: bytes,
    filename: str = "image.jpg",
    *,
    prompt: Optional[str] = None,
    model: Optional[str] = None,
    content_type: Optional[str] = None,
    detail: str = "auto",
    max_tokens: int = 500,
    client: Any = None,
    skip_moderation: bool = False,
) -> Dict[str, Any]:
    """
    完整流程：安全檢查 → 審核 → Vision 分析。

    回傳:
      {
        ok, description, summary, mime, ext, size,
        model, usage, moderation, preview_data_url?, error?
      }
    """
    meta = validate_image_bytes(file_bytes, filename, content_type)
    mime = meta["mime"]
    ext = meta["ext"]

    if client is None:
        from backend.openai_handler import get_openai_client

        client = get_openai_client()

    moderation = {"blocked": False, "skipped": True}
    if not skip_moderation:
        moderation = await moderate_image(file_bytes, mime, client=client)
        if moderation.get("blocked"):
            raise VisionSafetyError(
                "圖片未通過安全審核，已阻擋上傳／分析。"
                + (
                    f"（分類：{', '.join(moderation.get('flagged_categories') or [])}）"
                    if moderation.get("flagged_categories")
                    else ""
                ),
                "moderation_blocked",
            )

    vision_model = model or DEFAULT_VISION_MODEL
    if vision_model not in ("gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini"):
        # 僅允許已知支援 vision 的模型名稱，其餘退回 mini
        logger.warning(f"⚠️ 未知 Vision 模型 {vision_model}，改用 gpt-4o-mini")
        vision_model = "gpt-4o-mini"

    user_prompt = (prompt or "").strip() or (
        "請用繁體中文詳細描述這張圖片的內容，包括："
        "主要物體、場景、文字（若有 OCR）、情緒氛圍與值得注意的細節。"
        "條理清晰，不超過 300 字。"
    )

    b64 = base64.b64encode(file_bytes).decode("utf-8")
    data_url = f"data:{mime};base64,{b64}"

    import asyncio

    def _call():
        return client.chat.completions.create(
            model=vision_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是小宸光的視覺分析助手。用繁體中文溫暖、清楚的描述圖片。"
                        "若圖片含敏感暴力或色情內容，請簡短說明並拒答細節。"
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": data_url,
                                "detail": detail if detail in ("low", "high", "auto") else "auto",
                            },
                        },
                    ],
                },
            ],
            max_tokens=max_tokens,
            temperature=0.4,
        )

    try:
        response = await asyncio.to_thread(_call)
        description = (response.choices[0].message.content or "").strip()
        usage = getattr(response, "usage", None)
        usage_dict = {
            "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
            "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
            "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
        }
        preview = make_preview_data_url(file_bytes, mime)
        summary = f"圖片（{filename or 'image'+ext}）· AI 視覺分析已完成"
        if description:
            summary += f"：{description[:80]}{'…' if len(description) > 80 else ''}"

        # 記錄 token（若 tracker 可用）
        try:
            from backend.token_tracker import get_token_tracker

            get_token_tracker().record(
                user_id="vision",
                conversation_id="vision",
                model=vision_model,
                prompt_tokens=usage_dict["prompt_tokens"],
                completion_tokens=usage_dict["completion_tokens"],
                total_tokens=usage_dict["total_tokens"],
                endpoint="vision",
                meta={"filename": filename},
            )
        except Exception:
            pass

        return {
            "ok": True,
            "parsed": True,
            "type": "image",
            "content": description,
            "vision_analysis": description,
            "summary": summary,
            "mime": mime,
            "ext": ext,
            "size": meta["size"],
            "model": vision_model,
            "usage": usage_dict,
            "moderation": {
                "blocked": False,
                "flagged": moderation.get("flagged", False),
                "flagged_categories": moderation.get("flagged_categories", []),
            },
            "preview_data_url": preview,
        }
    except VisionSafetyError:
        raise
    except Exception as e:
        logger.error(f"❌ Vision 分析失敗: {e}")
        return {
            "ok": False,
            "parsed": False,
            "type": "image",
            "content": "",
            "vision_analysis": "",
            "summary": f"圖片檔案（{filename}），分析失敗",
            "mime": mime,
            "ext": ext,
            "size": meta["size"],
            "model": vision_model,
            "error": str(e),
            "moderation": moderation,
            "preview_data_url": make_preview_data_url(file_bytes, mime),
        }
