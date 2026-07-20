"""
語音相關 API

前端使用瀏覽器 SpeechRecognition / SpeechSynthesis；
後端提供：
- 能力與預設設定
- 語音偏好讀寫（Supabase user_preferences 或記憶體後備）
- TTS 友善文字清理
- 語音輸入事件紀錄（可選）
"""
from __future__ import annotations

import os
import re
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()
logger = logging.getLogger("voice_router")

# 進程內後備（無 DB 時）
_VOICE_PREFS: Dict[str, Dict[str, Any]] = {}


class VoiceSettings(BaseModel):
    lang: str = "zh-TW"
    rate: float = Field(default=1.0, ge=0.5, le=2.0)
    pitch: float = Field(default=1.0, ge=0.0, le=2.0)
    volume: float = Field(default=1.0, ge=0.0, le=1.0)
    auto_speak: bool = False
    car_mode: bool = False
    auto_send: bool = True
    continuous: bool = False
    strip_emojis_for_speech: bool = True
    voice_name: str = ""
    preferred_ai_voice_hint: str = "溫柔、清晰、中等語速"


class VoiceSettingsUpdate(BaseModel):
    user_id: str = "default_user"
    settings: VoiceSettings


class PrepareSpeechRequest(BaseModel):
    text: str
    strip_emojis: bool = True
    max_chars: int = Field(default=800, ge=50, le=4000)


class PrepareSpeechResponse(BaseModel):
    original_length: int
    speech_text: str
    truncated: bool
    tips: List[str] = []


class VoiceEventRequest(BaseModel):
    user_id: str = "default_user"
    conversation_id: Optional[str] = None
    event_type: str  # listen_start | listen_end | listen_error | speak_start | speak_end | car_mode_on | car_mode_off
    detail: Optional[Dict[str, Any]] = None
    transcript: Optional[str] = None


def _default_settings() -> Dict[str, Any]:
    return VoiceSettings().model_dump()


def sanitize_for_speech(text: str, strip_emojis: bool = True, max_chars: int = 800) -> tuple[str, bool]:
    """清理 markdown / 連結 / 代碼，適合車載朗讀。"""
    if not text:
        return "", False
    t = text
    t = re.sub(r"__XCG_META__[\s\S]*$", "", t)
    t = re.sub(r"__XCG_EVENT__[^\n]*", "", t)
    t = re.sub(r"```[\s\S]*?```", "（程式碼略過）", t)
    t = re.sub(r"`([^`]+)`", r"\1", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    t = re.sub(r"https?://\S+", "", t)
    t = re.sub(r"^#{1,6}\s+", "", t, flags=re.MULTILINE)
    t = re.sub(r"^\s*[-*+]\s+", "", t, flags=re.MULTILINE)
    t = re.sub(r"^\s*\d+\.\s+", "", t, flags=re.MULTILINE)
    t = re.sub(r"(\*\*|__)(.*?)\1", r"\2", t)
    t = re.sub(r"(\*|_)(.*?)\1", r"\2", t)
    t = re.sub(r"<[^>]+>", "", t)
    if strip_emojis:
        t = re.sub(
            r"[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE00-\uFE0F\u200D]",
            "",
            t,
        )
    t = re.sub(r"\s{2,}", " ", t).strip()
    truncated = False
    if max_chars and len(t) > max_chars:
        t = t[: max_chars - 1].rstrip() + "…"
        truncated = True
    return t, truncated


def build_voice_system_hint(voice_mode: bool = False, car_mode: bool = False) -> str:
    """給 PromptEngine / chat 使用的語音友善提示。"""
    if not voice_mode and not car_mode:
        return ""
    lines = [
        "### 🎙️ 語音 / 車載模式回覆規範",
        "1. 回覆請簡短口語化，優先 1～3 句完整話，方便語音朗讀。",
        "2. 避免 Markdown、程式碼區塊、表格、長列表與 URL。",
        "3. 少用表情符號與特殊符號；數字盡量用口語可讀寫法。",
        "4. 一次只問一個問題；結尾可輕聲確認使用者是否聽清楚。",
    ]
    if car_mode:
        lines.append(
            "5. 【車載模式】使用者可能在開車：句子更短、重點前置、避免需長時間閱讀的內容。"
        )
    return "\n".join(lines)


@router.get("/voice/status")
async def voice_status():
    """後端語音功能狀態與建議的前端預設。"""
    return {
        "status": "ok",
        "service": "voice",
        "frontend_apis": {
            "speech_recognition": "Web Speech API (SpeechRecognition / webkitSpeechRecognition)",
            "speech_synthesis": "Web Speech API (speechSynthesis)",
        },
        "backend_features": [
            "settings",
            "prepare_speech",
            "events",
            "voice_mode_prompt_hint",
        ],
        "defaults": _default_settings(),
        "car_mode": {
            "description": "自動語音：回覆朗讀結束後自動開麥，辨識結束後自動送出",
            "recommended": {
                "auto_speak": True,
                "auto_send": True,
                "continuous": False,
                "car_mode": True,
                "lang": "zh-TW",
                "rate": 1.05,
            },
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/voice/settings/{user_id}")
async def get_voice_settings(user_id: str):
    """讀取使用者語音偏好。"""
    settings = await _load_settings(user_id)
    return {"user_id": user_id, "settings": settings}


@router.put("/voice/settings")
async def put_voice_settings(body: VoiceSettingsUpdate):
    """儲存使用者語音偏好。"""
    user_id = (body.user_id or "default_user").strip() or "default_user"
    data = body.settings.model_dump()
    await _save_settings(user_id, data)
    return {"ok": True, "user_id": user_id, "settings": data}


@router.post("/voice/prepare-speech", response_model=PrepareSpeechResponse)
async def prepare_speech(body: PrepareSpeechRequest):
    """將 AI 回覆轉成適合 TTS 的純文字。"""
    speech, truncated = sanitize_for_speech(
        body.text,
        strip_emojis=body.strip_emojis,
        max_chars=body.max_chars,
    )
    tips = []
    if truncated:
        tips.append("內容過長已截斷，建議前端分段朗讀")
    if not speech:
        tips.append("清理後無內容可朗讀")
    return PrepareSpeechResponse(
        original_length=len(body.text or ""),
        speech_text=speech,
        truncated=truncated,
        tips=tips,
    )


@router.post("/voice/events")
async def voice_events(body: VoiceEventRequest):
    """紀錄語音使用事件（分析 / 除錯用，失敗不影響主流程）。"""
    allowed = {
        "listen_start",
        "listen_end",
        "listen_error",
        "speak_start",
        "speak_end",
        "car_mode_on",
        "car_mode_off",
        "auto_send",
    }
    if body.event_type not in allowed:
        raise HTTPException(status_code=400, detail=f"未知 event_type: {body.event_type}")

    payload = {
        "user_id": body.user_id,
        "conversation_id": body.conversation_id,
        "event_type": body.event_type,
        "detail": body.detail or {},
        "transcript": (body.transcript or "")[:500],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    logger.info(
        "🎙️ voice_event type=%s user=%s conv=%s",
        body.event_type,
        (body.user_id or "")[:12],
        (body.conversation_id or "")[:12],
    )
    # 盡力寫入 Supabase（表不存在則略過）
    try:
        from backend.supabase_handler import get_supabase

        sb = get_supabase()
        table = os.getenv("SUPABASE_VOICE_EVENTS_TABLE", "voice_events")
        sb.table(table).insert(payload).execute()
    except Exception as e:
        logger.debug("voice_events 未寫入 DB（可略過）: %s", e)

    return {"ok": True, "recorded": True}


@router.get("/voice/prompt-hint")
async def voice_prompt_hint(voice_mode: bool = True, car_mode: bool = False):
    """回傳可注入 system prompt 的語音規範文字。"""
    return {
        "hint": build_voice_system_hint(voice_mode=voice_mode, car_mode=car_mode),
        "voice_mode": voice_mode,
        "car_mode": car_mode,
    }


async def _load_settings(user_id: str) -> Dict[str, Any]:
    if user_id in _VOICE_PREFS:
        return {**_default_settings(), **_VOICE_PREFS[user_id]}
    try:
        from backend.supabase_handler import get_supabase

        sb = get_supabase()
        result = (
            sb.table("user_preferences")
            .select("voice_settings")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if result.data and result.data[0].get("voice_settings"):
            raw = result.data[0]["voice_settings"]
            if isinstance(raw, str):
                import json

                raw = json.loads(raw)
            if isinstance(raw, dict):
                merged = {**_default_settings(), **raw}
                _VOICE_PREFS[user_id] = merged
                return merged
    except Exception as e:
        logger.debug("load voice settings fallback: %s", e)
    return _default_settings()


async def _save_settings(user_id: str, settings: Dict[str, Any]) -> None:
    _VOICE_PREFS[user_id] = settings
    try:
        from backend.supabase_handler import get_supabase

        sb = get_supabase()
        # 嘗試 upsert user_preferences.voice_settings
        existing = (
            sb.table("user_preferences")
            .select("id")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if existing.data:
            sb.table("user_preferences").update(
                {"voice_settings": settings}
            ).eq("user_id", user_id).execute()
        else:
            sb.table("user_preferences").insert(
                {"user_id": user_id, "voice_settings": settings}
            ).execute()
        logger.info("✅ voice settings saved user=%s", user_id[:12])
    except Exception as e:
        logger.warning("⚠️ voice settings 僅存記憶體: %s", e)
