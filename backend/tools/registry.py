"""
Tool Use / Function Calling 框架

- 工具註冊表（allowlist）
- 安全控管：禁止危險工具、參數驗證、逾時、次數限制
- 統一執行入口，供 chat_router 使用
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("tools.registry")

ToolHandler = Callable[..., Awaitable[str]]


# 明確禁止的工具名稱（即使被注入定義也不執行）
BLOCKED_TOOL_NAMES = {
    "shell",
    "bash",
    "cmd",
    "powershell",
    "exec",
    "eval",
    "python",
    "run_code",
    "code_interpreter",
    "file_write",
    "write_file",
    "delete_file",
    "rm",
    "http_request",
    "fetch_url_raw",
    "subprocess",
    "os_system",
    "sql",
    "database",
}


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: ToolHandler
    risk_level: str = "low"  # low | medium | high
    timeout_seconds: float = 15.0
    enabled: bool = True
    required: List[str] = field(default_factory=list)
    display_name: str = ""
    icon: str = "🔧"
    retry: int = 0  # 暫時性錯誤重試次數


@dataclass
class ToolCallResult:
    name: str
    tool_call_id: str
    arguments: Dict[str, Any]
    ok: bool
    content: str
    duration_ms: int
    error: Optional[str] = None
    error_code: Optional[str] = None
    display_name: str = ""
    icon: str = "🔧"
    index: int = 0
    total: int = 0


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, ToolSpec] = {}
        self.max_tools_per_turn = int(os.getenv("MAX_TOOLS_PER_TURN", "3"))
        self.max_arg_json_len = int(os.getenv("MAX_TOOL_ARG_JSON_LEN", "2000"))

    def register(self, spec: ToolSpec) -> None:
        name = (spec.name or "").strip()
        if not name:
            raise ValueError("tool name required")
        if name.lower() in BLOCKED_TOOL_NAMES:
            raise ValueError(f"tool name blocked: {name}")
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", name):
            raise ValueError(f"invalid tool name: {name}")
        self._tools[name] = spec
        logger.info(f"🔧 註冊工具: {name} (risk={spec.risk_level})")

    def get(self, name: str) -> Optional[ToolSpec]:
        return self._tools.get(name)

    def list_enabled(self) -> List[ToolSpec]:
        return [t for t in self._tools.values() if t.enabled]

    def openai_tool_definitions(self) -> List[Dict[str, Any]]:
        """產生 OpenAI tools 陣列。"""
        defs = []
        for t in self.list_enabled():
            if t.risk_level == "high":
                # high risk 預設不暴露給模型
                continue
            defs.append(
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
            )
        return defs

    def is_allowed(self, name: str) -> Tuple[bool, str]:
        if not name:
            return False, "empty tool name"
        key = name.strip()
        if key.lower() in BLOCKED_TOOL_NAMES:
            return False, f"blocked tool: {key}"
        if key not in self._tools:
            return False, f"unknown tool: {key}"
        spec = self._tools[key]
        if not spec.enabled:
            return False, f"disabled tool: {key}"
        if spec.risk_level == "high":
            return False, f"high-risk tool denied: {key}"
        return True, "ok"

    def _validate_args(self, spec: ToolSpec, args: Dict[str, Any]) -> Tuple[bool, str]:
        if not isinstance(args, dict):
            return False, "arguments must be object"
        raw = json.dumps(args, ensure_ascii=False)
        if len(raw) > self.max_arg_json_len:
            return False, "arguments too large"
        for req in spec.required or []:
            if req not in args or args.get(req) in (None, ""):
                return False, f"missing required arg: {req}"
        # 字串參數基本消毒：禁止明顯注入片段
        for k, v in args.items():
            if isinstance(v, str):
                if len(v) > 1000:
                    return False, f"arg too long: {k}"
                lower = v.lower()
                if any(
                    bad in lower
                    for bad in (
                        "rm -rf",
                        "drop table",
                        "; shutdown",
                        "powershell",
                        "/etc/passwd",
                    )
                ):
                    return False, f"suspicious arg content: {k}"
        return True, "ok"

    def _coerce_and_filter_args(self, spec: ToolSpec, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """依 schema 粗略轉型，並只保留 handler 可接受參數。"""
        import inspect

        props = (spec.parameters or {}).get("properties") or {}
        raw = dict(arguments or {})
        out: Dict[str, Any] = {}
        for key, val in raw.items():
            schema = props.get(key) or {}
            t = schema.get("type")
            try:
                if t == "integer" and val is not None and not isinstance(val, bool):
                    out[key] = int(val)
                elif t == "number" and val is not None and not isinstance(val, bool):
                    out[key] = float(val)
                elif t == "boolean" and not isinstance(val, bool):
                    if isinstance(val, str):
                        out[key] = val.lower() in ("1", "true", "yes")
                    else:
                        out[key] = bool(val)
                else:
                    out[key] = val
            except (TypeError, ValueError):
                out[key] = val

        try:
            sig = inspect.signature(spec.handler)
            allowed = set(sig.parameters.keys())
            # 允許 **kwargs
            if any(
                p.kind == inspect.Parameter.VAR_KEYWORD
                for p in sig.parameters.values()
            ):
                return out
            return {k: v for k, v in out.items() if k in allowed}
        except Exception:
            return out

    def _friendly_error_content(self, name: str, code: str, detail: str = "") -> str:
        messages = {
            "denied": f"⚠️ 工具「{name}」不被允許使用。",
            "invalid_args": f"⚠️ 工具「{name}」參數不正確" + (f"：{detail}" if detail else "。"),
            "timeout": f"⏰ 工具「{name}」執行逾時，請稍後再試。",
            "parse_error": f"⚠️ 無法解析工具「{name}」的參數。",
            "type_error": f"⚠️ 工具「{name}」參數型別不符。",
            "error": f"❌ 工具「{name}」執行失敗" + (f"（{detail}）" if detail else "。"),
            "empty": f"ℹ️ 工具「{name}」沒有回傳內容。",
        }
        return messages.get(code, messages["error"])

    def _is_transient_error(self, err: Exception) -> bool:
        msg = str(err).lower()
        return any(
            k in msg
            for k in (
                "timeout",
                "timed out",
                "temporarily",
                "connection",
                "reset",
                "503",
                "502",
                "429",
            )
        )

    async def execute(
        self,
        name: str,
        arguments: Dict[str, Any],
        tool_call_id: str = "unknown",
        context: Optional[Dict[str, Any]] = None,
        index: int = 0,
        total: int = 0,
    ) -> ToolCallResult:
        context = context or {}
        display = name
        icon = "🔧"
        if name in self._tools:
            display = self._tools[name].display_name or name
            icon = self._tools[name].icon or icon

        def _fail(code: str, content: str, args=None, err=None, ms=0):
            return ToolCallResult(
                name=name or "unknown",
                tool_call_id=tool_call_id,
                arguments=args if args is not None else (arguments or {}),
                ok=False,
                content=content,
                duration_ms=ms,
                error=err or code,
                error_code=code,
                display_name=display,
                icon=icon,
                index=index,
                total=total,
            )

        allowed, reason = self.is_allowed(name)
        if not allowed:
            logger.warning(f"🚫 工具拒絕: {name} ({reason})")
            return _fail("denied", self._friendly_error_content(name, "denied", reason), err=reason)

        spec = self._tools[name]
        display = spec.display_name or name
        icon = spec.icon or icon

        args = dict(arguments or {})
        # 注入 context（例如 user_id 給 reminder）
        if context.get("user_id") and "user_id" not in args:
            props = (spec.parameters or {}).get("properties") or {}
            if "user_id" in props or name in ("manage_reminder",):
                args["user_id"] = context["user_id"]

        ok_args, arg_reason = self._validate_args(spec, args)
        if not ok_args:
            return _fail(
                "invalid_args",
                self._friendly_error_content(name, "invalid_args", arg_reason),
                args=args,
                err=arg_reason,
            )

        call_args = self._coerce_and_filter_args(spec, args)
        attempts = 1 + max(0, int(spec.retry or 0))
        started = time.perf_counter()
        last_err: Optional[Exception] = None

        for attempt in range(attempts):
            try:
                result = await asyncio.wait_for(
                    spec.handler(**call_args),
                    timeout=spec.timeout_seconds,
                )
                content = str(result) if result is not None else ""
                max_out = int(os.getenv("MAX_TOOL_OUTPUT_CHARS", "6000"))
                if len(content) > max_out:
                    content = content[:max_out] + "\n...(truncated)"
                duration_ms = int((time.perf_counter() - started) * 1000)
                # 工具自行回傳錯誤碼時標為失敗（可選）
                soft_fail = content.startswith("[") and any(
                    tag in content
                    for tag in (
                        "[TOOL_",
                        "[SEARCH_",
                        "[WEATHER_ERROR",
                        "[WEATHER_TIMEOUT",
                        "[REMINDER_ERROR",
                        "[CALC_ERROR",
                        "[CONVERT_ERROR",
                    )
                )
                logger.info(
                    f"{'⚠️' if soft_fail else '✅'} 工具完成 {name} "
                    f"{duration_ms}ms attempt={attempt+1} len={len(content)}"
                )
                return ToolCallResult(
                    name=name,
                    tool_call_id=tool_call_id,
                    arguments=args,
                    ok=not soft_fail,
                    content=content or self._friendly_error_content(name, "empty"),
                    duration_ms=duration_ms,
                    error=None if not soft_fail else "tool_reported_error",
                    error_code=None if not soft_fail else "tool_reported_error",
                    display_name=display,
                    icon=icon,
                    index=index,
                    total=total,
                )
            except asyncio.TimeoutError as e:
                last_err = e
                if attempt + 1 < attempts:
                    await asyncio.sleep(0.4 * (attempt + 1))
                    continue
                duration_ms = int((time.perf_counter() - started) * 1000)
                logger.warning(f"⏰ 工具逾時 {name}")
                return _fail(
                    "timeout",
                    self._friendly_error_content(name, "timeout"),
                    args=args,
                    err="timeout",
                    ms=duration_ms,
                )
            except TypeError as e:
                duration_ms = int((time.perf_counter() - started) * 1000)
                return _fail(
                    "type_error",
                    self._friendly_error_content(name, "type_error", str(e)),
                    args=args,
                    err=str(e),
                    ms=duration_ms,
                )
            except Exception as e:
                last_err = e
                if attempt + 1 < attempts and self._is_transient_error(e):
                    logger.warning(f"↻ 工具暫態錯誤重試 {name}: {e}")
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                duration_ms = int((time.perf_counter() - started) * 1000)
                logger.exception(f"❌ 工具執行失敗 {name}: {e}")
                return _fail(
                    "error",
                    self._friendly_error_content(name, "error", type(e).__name__),
                    args=args,
                    err=str(e),
                    ms=duration_ms,
                )

        duration_ms = int((time.perf_counter() - started) * 1000)
        return _fail(
            "error",
            self._friendly_error_content(name, "error", str(last_err or "")),
            args=args,
            err=str(last_err or "unknown"),
            ms=duration_ms,
        )

    async def execute_openai_tool_calls(
        self,
        tool_calls: list,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[ToolCallResult]:
        """執行 OpenAI tool_calls（批次，含安全截斷）。"""
        results: List[ToolCallResult] = []
        async for item in self.iter_openai_tool_calls(tool_calls, context=context):
            if item.get("type") == "result":
                results.append(item["result"])
        return results

    async def iter_openai_tool_calls(
        self,
        tool_calls: list,
        context: Optional[Dict[str, Any]] = None,
    ):
        """
        逐步執行 tool_calls，yield 進度事件：
          {"type":"start","index","total","name",...}
          {"type":"result","result": ToolCallResult}
        """
        if not tool_calls:
            return

        limited = list(tool_calls)[: self.max_tools_per_turn]
        if len(tool_calls) > self.max_tools_per_turn:
            logger.warning(
                f"⚠️ 工具呼叫過多，截斷為前 {self.max_tools_per_turn} 個"
            )

        total = len(limited)
        for idx, tool_call in enumerate(limited):
            try:
                fn_name = tool_call.function.name
                raw_args = tool_call.function.arguments or "{}"
                args = (
                    json.loads(raw_args)
                    if isinstance(raw_args, str)
                    else dict(raw_args)
                )
            except Exception as e:
                name = getattr(
                    getattr(tool_call, "function", None), "name", "unknown"
                )
                result = ToolCallResult(
                    name=name,
                    tool_call_id=getattr(tool_call, "id", "unknown"),
                    arguments={},
                    ok=False,
                    content=self._friendly_error_content(name, "parse_error", str(e)),
                    duration_ms=0,
                    error=str(e),
                    error_code="parse_error",
                    display_name=name,
                    index=idx,
                    total=total,
                )
                yield {"type": "start", "index": idx, "total": total, "name": name}
                yield {"type": "result", "result": result}
                continue

            tool_call_id = getattr(tool_call, "id", "unknown")
            spec = self._tools.get(fn_name)
            yield {
                "type": "start",
                "index": idx,
                "total": total,
                "name": fn_name,
                "display_name": (spec.display_name if spec else fn_name),
                "icon": (spec.icon if spec else "🔧"),
                "arguments": args,
                "tool_call_id": tool_call_id,
            }
            result = await self.execute(
                fn_name,
                args,
                tool_call_id=tool_call_id,
                context=context,
                index=idx,
                total=total,
            )
            yield {"type": "result", "result": result}


_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """取得全域工具註冊表（延遲初始化並註冊內建工具）。"""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
        _register_builtin_tools(_registry)
    return _registry


def _register_builtin_tools(registry: ToolRegistry) -> None:
    from backend.tools.web_search import web_search
    from backend.tools.time_tool import get_current_time
    from backend.tools.calculator import calculate
    from backend.tools.weather import get_weather
    from backend.tools.reminder import manage_reminder
    from backend.tools.unit_convert import convert_units

    import datetime

    year = datetime.datetime.now().year

    registry.register(
        ToolSpec(
            name="web_search",
            display_name="Web 搜尋",
            icon="🔍",
            description=(
                f"搜尋網路取得最新資訊、新聞、時事或事實查核。"
                f"適用：即時資訊、最新事件、不確定是否過時的知識。"
                f"目前年份為 {year}。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            f"搜尋關鍵字或問題。建議必要時加上年份（如 {year}）。"
                        ),
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "最多回傳幾筆結果（1-5，預設 5）",
                        "minimum": 1,
                        "maximum": 5,
                    },
                },
                "required": ["query"],
            },
            handler=web_search,
            risk_level="medium",
            timeout_seconds=float(os.getenv("WEB_SEARCH_TIMEOUT", "12")),
            required=["query"],
            retry=1,
        )
    )

    registry.register(
        ToolSpec(
            name="get_current_time",
            display_name="目前時間",
            icon="🕒",
            description=(
                "取得目前日期與時間（可指定時區）。"
                "適用：用戶問現在幾點、今天日期、時差等。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "timezone": {
                        "type": "string",
                        "description": (
                            "IANA 時區，例如 Asia/Taipei、UTC、America/New_York。"
                            "預設 Asia/Taipei。"
                        ),
                    }
                },
                "required": [],
            },
            handler=get_current_time,
            risk_level="low",
            timeout_seconds=3.0,
            required=[],
        )
    )

    registry.register(
        ToolSpec(
            name="calculate",
            display_name="計算機",
            icon="🧮",
            description=(
                "安全計算數學運算式，支援加減乘除、次方、括號與常用函數"
                "（sin/cos/sqrt/log 等）。不要用於程式執行。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "數學運算式，例如 2*(3+4)^2 或 sqrt(16)+log(10)",
                    }
                },
                "required": ["expression"],
            },
            handler=calculate,
            risk_level="low",
            timeout_seconds=3.0,
            required=["expression"],
        )
    )

    registry.register(
        ToolSpec(
            name="get_weather",
            display_name="查天氣",
            icon="🌤️",
            description=(
                "查詢指定城市/地區的目前天氣與短預報（1-3 天）。"
                "適用：氣溫、下雨、是否帶傘等。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "地點，例如：台北、高雄、Tokyo、New York",
                    },
                    "days": {
                        "type": "integer",
                        "description": "預報天數 1-3，預設 1",
                        "minimum": 1,
                        "maximum": 3,
                    },
                },
                "required": ["location"],
            },
            handler=get_weather,
            risk_level="low",
            timeout_seconds=12.0,
            required=["location"],
            retry=1,
        )
    )

    registry.register(
        ToolSpec(
            name="manage_reminder",
            display_name="提醒",
            icon="⏰",
            description=(
                "管理個人提醒/待辦。action=set 新增、list 列出、delete 刪除。"
                "設定時提供 text 與 when（如 30m、2h、明天 09:00）。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "set | list | delete",
                        "enum": ["set", "list", "delete"],
                    },
                    "text": {
                        "type": "string",
                        "description": "提醒內容（set 時必填）",
                    },
                    "when": {
                        "type": "string",
                        "description": "時間，如 30m、2h、1d、明天 09:00、2026-07-21 18:00",
                    },
                    "reminder_id": {
                        "type": "string",
                        "description": "刪除時的提醒 ID",
                    },
                    "user_id": {
                        "type": "string",
                        "description": "使用者 ID（系統可自動填入）",
                    },
                },
                "required": ["action"],
            },
            handler=manage_reminder,
            risk_level="low",
            timeout_seconds=5.0,
            required=["action"],
        )
    )

    registry.register(
        ToolSpec(
            name="convert_units",
            display_name="單位換算",
            icon="↔️",
            description=(
                "單位換算：長度（m/km/cm/mi/ft）、重量（kg/g/lb）、溫度（C/F/K）。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "value": {
                        "type": "number",
                        "description": "數值",
                    },
                    "from_unit": {
                        "type": "string",
                        "description": "來源單位，如 km、lb、C",
                    },
                    "to_unit": {
                        "type": "string",
                        "description": "目標單位，如 mi、kg、F",
                    },
                },
                "required": ["value", "from_unit", "to_unit"],
            },
            handler=convert_units,
            risk_level="low",
            timeout_seconds=3.0,
            required=["value", "from_unit", "to_unit"],
        )
    )


def get_openai_tool_definitions() -> List[Dict[str, Any]]:
    return get_tool_registry().openai_tool_definitions()
