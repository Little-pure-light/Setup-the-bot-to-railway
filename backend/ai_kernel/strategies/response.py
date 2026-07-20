"""Response Strategy — 語音 / 車載 / 預設。"""
from __future__ import annotations

from backend.ai_kernel.models import KernelRequest, ModelConfig, ResponseStrategy


def select_response_strategy(request: KernelRequest) -> tuple[ModelConfig, ResponseStrategy]:
    if request.ai_id == "story_master_v1":
        model = "gpt-4o"
        temp = 0.95
    else:
        model = "gpt-4o-mini"
        temp = 0.8

    if request.car_mode:
        strategy = ResponseStrategy(
            name="car",
            max_tokens=600,
            temperature=temp,
            voice_friendly=True,
            car_mode=True,
            system_hint="car_mode_short",
        )
    elif request.voice_mode or request.speak_response:
        strategy = ResponseStrategy(
            name="voice",
            max_tokens=800,
            temperature=temp,
            voice_friendly=True,
            car_mode=False,
            system_hint="voice_mode",
        )
    else:
        strategy = ResponseStrategy(
            name="default",
            max_tokens=2000,
            temperature=temp,
            voice_friendly=False,
            car_mode=False,
        )

    cfg = ModelConfig(model=model, temperature=temp, max_tokens=strategy.max_tokens)
    return cfg, strategy
