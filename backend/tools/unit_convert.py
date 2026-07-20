"""簡單單位換算工具"""
from __future__ import annotations

import logging
from typing import Dict, Tuple

logger = logging.getLogger("tools.unit_convert")

# 基準單位因子
_LENGTH_TO_M: Dict[str, float] = {
    "m": 1.0,
    "meter": 1.0,
    "meters": 1.0,
    "km": 1000.0,
    "cm": 0.01,
    "mm": 0.001,
    "mi": 1609.344,
    "mile": 1609.344,
    "ft": 0.3048,
    "feet": 0.3048,
    "in": 0.0254,
    "inch": 0.0254,
}

_WEIGHT_TO_KG: Dict[str, float] = {
    "kg": 1.0,
    "g": 0.001,
    "mg": 1e-6,
    "lb": 0.45359237,
    "lbs": 0.45359237,
    "oz": 0.028349523125,
}

_TEMP = {"c", "celsius", "f", "fahrenheit", "k", "kelvin"}


def _norm(u: str) -> str:
    return (u or "").strip().lower().replace("°", "")


async def convert_units(value: float, from_unit: str, to_unit: str) -> str:
    """
    換算 value from_unit -> to_unit
    支援長度、重量、溫度。
    """
    try:
        val = float(value)
    except (TypeError, ValueError):
        return "[CONVERT_ERROR] value 必須是數字"

    a = _norm(from_unit)
    b = _norm(to_unit)
    if not a or not b:
        return "[CONVERT_ERROR] 請提供 from_unit 與 to_unit"

    try:
        # 溫度
        if a in _TEMP and b in _TEMP:
            # to C
            if a in ("c", "celsius"):
                c = val
            elif a in ("f", "fahrenheit"):
                c = (val - 32) * 5 / 9
            else:
                c = val - 273.15
            if b in ("c", "celsius"):
                out = c
            elif b in ("f", "fahrenheit"):
                out = c * 9 / 5 + 32
            else:
                out = c + 273.15
            return f"換算結果：{val} {from_unit} = {round(out, 6)} {to_unit}"

        if a in _LENGTH_TO_M and b in _LENGTH_TO_M:
            meters = val * _LENGTH_TO_M[a]
            out = meters / _LENGTH_TO_M[b]
            return f"換算結果：{val} {from_unit} = {round(out, 6)} {to_unit}"

        if a in _WEIGHT_TO_KG and b in _WEIGHT_TO_KG:
            kg = val * _WEIGHT_TO_KG[a]
            out = kg / _WEIGHT_TO_KG[b]
            return f"換算結果：{val} {from_unit} = {round(out, 6)} {to_unit}"

        return (
            f"[CONVERT_ERROR] 不支援的單位組合 {from_unit} → {to_unit}。"
            "支援：m/km/cm/mi/ft、kg/g/lb、C/F/K"
        )
    except Exception as e:
        logger.warning(f"convert error: {e}")
        return "[CONVERT_ERROR] 換算失敗"
