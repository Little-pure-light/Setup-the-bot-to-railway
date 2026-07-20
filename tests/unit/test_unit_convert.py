"""backend/tools/unit_convert.py 單元測試"""
import pytest

from backend.tools.unit_convert import convert_units


@pytest.mark.unit
@pytest.mark.asyncio
async def test_km_to_miles():
    r = await convert_units(10, "km", "mi")
    assert "換算結果" in r
    # 10 km ≈ 6.213712 mi
    assert "6.21" in r


@pytest.mark.unit
@pytest.mark.asyncio
async def test_kg_to_lb():
    r = await convert_units(1, "kg", "lb")
    assert "換算結果" in r
    assert "2.20" in r  # ≈ 2.204623


@pytest.mark.unit
@pytest.mark.asyncio
async def test_celsius_to_fahrenheit():
    r = await convert_units(0, "C", "F")
    assert "換算結果" in r
    assert "32" in r


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fahrenheit_to_celsius():
    r = await convert_units(212, "F", "C")
    assert "換算結果" in r
    assert "100" in r


@pytest.mark.unit
@pytest.mark.asyncio
async def test_same_unit_length():
    r = await convert_units(5, "m", "m")
    assert "換算結果" in r
    assert "5" in r


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unsupported_units():
    r = await convert_units(1, "lightyear", "parsec")
    assert "[CONVERT_ERROR]" in r
    assert "不支援" in r


@pytest.mark.unit
@pytest.mark.asyncio
async def test_non_numeric_value():
    r = await convert_units("abc", "km", "mi")  # type: ignore[arg-type]
    assert "[CONVERT_ERROR]" in r
    assert "數字" in r


@pytest.mark.unit
@pytest.mark.asyncio
async def test_missing_unit():
    r = await convert_units(1, "", "mi")
    assert "[CONVERT_ERROR]" in r


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cross_category_not_supported():
    r = await convert_units(1, "kg", "km")
    assert "[CONVERT_ERROR]" in r


@pytest.mark.unit
@pytest.mark.asyncio
async def test_kelvin_to_celsius():
    r = await convert_units(273.15, "K", "C")
    assert "換算結果" in r
    assert "0" in r
