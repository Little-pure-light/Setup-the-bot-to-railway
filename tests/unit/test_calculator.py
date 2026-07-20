"""backend/tools/calculator.py 單元測試"""
import pytest

from backend.tools.calculator import calculate


@pytest.mark.unit
@pytest.mark.asyncio
async def test_add_subtract_multiply_divide():
    r = await calculate("1 + 2 * 3 - 4 / 2")
    assert "計算結果" in r
    assert "= 5" in r or "= 5.0" in r


@pytest.mark.unit
@pytest.mark.asyncio
async def test_parentheses():
    r = await calculate("(1 + 2) * 3")
    assert "計算結果" in r
    assert "= 9" in r


@pytest.mark.unit
@pytest.mark.asyncio
async def test_power():
    r = await calculate("2 ** 10")
    assert "計算結果" in r
    assert "1024" in r


@pytest.mark.unit
@pytest.mark.asyncio
async def test_negative_numbers():
    r = await calculate("-5 + 3")
    assert "計算結果" in r
    assert "-2" in r


@pytest.mark.unit
@pytest.mark.asyncio
async def test_decimals():
    r = await calculate("0.1 + 0.2")
    assert "計算結果" in r
    # 允許浮點誤差顯示
    assert "0.3" in r


@pytest.mark.unit
@pytest.mark.asyncio
async def test_divide_by_zero():
    r = await calculate("1 / 0")
    assert "[CALC_ERROR]" in r
    assert "除以零" in r


@pytest.mark.unit
@pytest.mark.asyncio
async def test_invalid_expression():
    r = await calculate("1 +")
    assert "[CALC_ERROR]" in r


@pytest.mark.unit
@pytest.mark.asyncio
async def test_dangerous_strings_denied():
    r = await calculate("__import__('os').system('ls')")
    assert "[CALC_DENIED]" in r or "[CALC_ERROR]" in r


@pytest.mark.unit
@pytest.mark.asyncio
async def test_eval_injection_denied():
    r = await calculate("eval('1+1')")
    assert "[CALC_DENIED]" in r


@pytest.mark.unit
@pytest.mark.asyncio
async def test_too_long_expression():
    r = await calculate("1+" * 150 + "1")
    assert "[CALC_ERROR]" in r
    assert "過長" in r


@pytest.mark.unit
@pytest.mark.asyncio
async def test_empty_expression():
    r = await calculate("")
    assert "[CALC_ERROR]" in r
    assert "空" in r


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sqrt_function():
    r = await calculate("sqrt(16)")
    assert "計算結果" in r
    assert "4" in r
