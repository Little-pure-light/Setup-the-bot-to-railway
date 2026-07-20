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


@dataclass
class ToolCallResult:
    name: str
    tool_call_id: str
    arguments: Dict[str, Any]
    ok: bool
    content: str
    duration_ms: int
    error: Optional[str] = None


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

    async def execute(
        self,
        name: str,
        arguments: Dict[str, Any],
        tool_call_id: str = "unknown",
    ) -> ToolCallResult:
        allowed, reason = self.is_allowed(name)
        if not allowed:
            logger.warning(f"🚫 工具拒絕: {name} ({reason})")
            return ToolCallResult(
                name=name or "unknown",
                tool_call_id=tool_call_id,
                arguments=arguments or {},
                ok=False,
                content=f"[TOOL_DENIED] {reason}",
                duration_ms=0,
                error=reason,
            )

        spec = self._tools[name]
        ok_args, arg_reason = self._validate_args(spec, arguments or {})
        if not ok_args:
            return ToolCallResult(
                name=name,
                tool_call_id=tool_call_id,
                arguments=arguments or {},
                ok=False,
                content=f"[TOOL_INVALID_ARGS] {arg_reason}",
                duration_ms=0,
                error=arg_reason,
            )

        started = time.perf_counter()
        try:
            result = await asyncio.wait_for(
                spec.handler(**(arguments or {})),
                timeout=spec.timeout_seconds,
            )
            content = str(result) if result is not None else ""
            # 限制工具輸出長度，避免洗版 context
            max_out = int(os.getenv("MAX_TOOL_OUTPUT_CHARS", "6000"))
            if len(content) > max_out:
                content = content[:max_out] + "\n...(truncated)"
            duration_ms = int((time.perf_counter() - started) * 1000)
            logger.info(f"✅ 工具完成 {name} {duration_ms}ms len={len(content)}")
            return ToolCallResult(
                name=name,
                tool_call_id=tool_call_id,
                arguments=arguments or {},
                ok=True,
                content=content or "[TOOL_EMPTY] 無結果",
                duration_ms=duration_ms,
            )
        except asyncio.TimeoutError:
            duration_ms = int((time.perf_counter() - started) * 1000)
            logger.warning(f"⏰ 工具逾時 {name}")
            return ToolCallResult(
                name=name,
                tool_call_id=tool_call_id,
                arguments=arguments or {},
                ok=False,
                content=f"[TOOL_TIMEOUT] {name} 逾時",
                duration_ms=duration_ms,
                error="timeout",
            )
        except TypeError as e:
            duration_ms = int((time.perf_counter() - started) * 1000)
            return ToolCallResult(
                name=name,
                tool_call_id=tool_call_id,
                arguments=arguments or {},
                ok=False,
                content=f"[TOOL_ARG_ERROR] 參數不符合工具介面: {e}",
                duration_ms=duration_ms,
                error=str(e),
            )
        except Exception as e:
            duration_ms = int((time.perf_counter() - started) * 1000)
            logger.exception(f"❌ 工具執行失敗 {name}: {e}")
            return ToolCallResult(
                name=name,
                tool_call_id=tool_call_id,
                arguments=arguments or {},
                ok=False,
                content=f"[TOOL_ERROR] {name} 執行失敗",
                duration_ms=duration_ms,
                error=str(e),
            )

    async def execute_openai_tool_calls(self, tool_calls: list) -> List[ToolCallResult]:
        """
        執行 OpenAI 回傳的 tool_calls 列表（含安全截斷）。
        """
        results: List[ToolCallResult] = []
        if not tool_calls:
            return results

        limited = list(tool_calls)[: self.max_tools_per_turn]
        if len(tool_calls) > self.max_tools_per_turn:
            logger.warning(
                f"⚠️ 工具呼叫過多，截斷為前 {self.max_tools_per_turn} 個"
            )

        for tool_call in limited:
            try:
                fn_name = tool_call.function.name
                raw_args = tool_call.function.arguments or "{}"
                args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
            except Exception as e:
                results.append(
                    ToolCallResult(
                        name=getattr(getattr(tool_call, "function", None), "name", "unknown"),
                        tool_call_id=getattr(tool_call, "id", "unknown"),
                        arguments={},
                        ok=False,
                        content=f"[TOOL_PARSE_ERROR] {e}",
                        duration_ms=0,
                        error=str(e),
                    )
                )
                continue

            tool_call_id = getattr(tool_call, "id", "unknown")
            result = await self.execute(fn_name, args, tool_call_id=tool_call_id)
            results.append(result)

        return results


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

    import datetime

    year = datetime.datetime.now().year

    registry.register(
        ToolSpec(
            name="web_search",
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
        )
    )

    registry.register(
        ToolSpec(
            name="get_current_time",
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


def get_openai_tool_definitions() -> List[Dict[str, Any]]:
    return get_tool_registry().openai_tool_definitions()
