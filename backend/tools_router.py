"""工具清單 API（前端可顯示可用工具）"""
from fastapi import APIRouter
from backend.tools import get_tool_registry

router = APIRouter()


@router.get("/tools")
async def list_tools():
    registry = get_tool_registry()
    tools = []
    for t in registry.list_enabled():
        if t.risk_level == "high":
            continue
        tools.append(
            {
                "name": t.name,
                "description": t.description,
                "risk_level": t.risk_level,
                "timeout_seconds": t.timeout_seconds,
                "parameters": t.parameters,
            }
        )
    return {
        "tools": tools,
        "max_tools_per_turn": registry.max_tools_per_turn,
        "blocked_examples": ["shell", "exec", "write_file", "python"],
    }
