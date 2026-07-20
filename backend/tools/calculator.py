"""
安全計算機工具

僅允許數學運算的 AST 子集，禁止任意程式執行。
"""
from __future__ import annotations

import ast
import logging
import math
import operator
from typing import Any

logger = logging.getLogger("tools.calculator")

_ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_ALLOWED_UNARY = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

_ALLOWED_FUNCS = {
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "exp": math.exp,
    "abs": abs,
    "round": round,
    "floor": math.floor,
    "ceil": math.ceil,
    "pow": pow,
}

_ALLOWED_CONSTS = {
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
}


class SafeEvalError(ValueError):
    pass


def _eval_node(node: ast.AST) -> Any:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)

    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value

    # py<3.8 compat style (Num)
    if isinstance(node, ast.Num):  # type: ignore[attr-defined]
        return node.n

    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _ALLOWED_BINOPS:
            raise SafeEvalError(f"不支援的運算: {op_type.__name__}")
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if op_type in (ast.Div, ast.FloorDiv, ast.Mod) and right == 0:
            raise SafeEvalError("除以零")
        if op_type is ast.Pow and (abs(left) > 1e6 or abs(right) > 100):
            raise SafeEvalError("次方過大")
        return _ALLOWED_BINOPS[op_type](left, right)

    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _ALLOWED_UNARY:
            raise SafeEvalError(f"不支援的一元運算: {op_type.__name__}")
        return _ALLOWED_UNARY[op_type](_eval_node(node.operand))

    if isinstance(node, ast.Name):
        if node.id in _ALLOWED_CONSTS:
            return _ALLOWED_CONSTS[node.id]
        raise SafeEvalError(f"不允許的名稱: {node.id}")

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise SafeEvalError("只允許呼叫具名函數")
        fn_name = node.func.id
        if fn_name not in _ALLOWED_FUNCS:
            raise SafeEvalError(f"不允許的函數: {fn_name}")
        if node.keywords:
            raise SafeEvalError("不支援關鍵字參數")
        args = [_eval_node(a) for a in node.args]
        if len(args) > 3:
            raise SafeEvalError("參數過多")
        return _ALLOWED_FUNCS[fn_name](*args)

    raise SafeEvalError(f"不支援的語法: {type(node).__name__}")


async def calculate(expression: str) -> str:
    """安全計算 expression，回傳可讀字串。"""
    expr = (expression or "").strip()
    if not expr:
        return "[CALC_ERROR] 運算式為空"
    if len(expr) > 200:
        return "[CALC_ERROR] 運算式過長"

    # 快速阻擋明顯非數學內容
    banned = ("import", "os.", "sys.", "__", "lambda", "open(", "eval", "exec")
    lower = expr.lower()
    if any(b in lower for b in banned):
        return "[CALC_DENIED] 不允許的內容"

    try:
        tree = ast.parse(expr, mode="eval")
        value = _eval_node(tree)
        if isinstance(value, float):
            # 漂亮格式
            if value.is_integer():
                value = int(value)
            else:
                value = round(value, 10)
        return f"計算結果：{expression} = {value}"
    except SafeEvalError as e:
        return f"[CALC_ERROR] {e}"
    except Exception as e:
        logger.warning(f"calculate failed: {e}")
        return "[CALC_ERROR] 無法計算此運算式"
