"""
工具模組：Function Calling 框架 + 內建工具
"""
from .web_search import web_search
from .time_tool import get_current_time
from .calculator import calculate
from .weather import get_weather
from .reminder import manage_reminder
from .unit_convert import convert_units
from .registry import (
    get_tool_registry,
    get_openai_tool_definitions,
    ToolRegistry,
    ToolCallResult,
)
from .tool_definitions import TOOL_DEFINITIONS

__all__ = [
    "web_search",
    "get_current_time",
    "calculate",
    "get_weather",
    "manage_reminder",
    "convert_units",
    "get_tool_registry",
    "get_openai_tool_definitions",
    "ToolRegistry",
    "ToolCallResult",
    "TOOL_DEFINITIONS",
]
