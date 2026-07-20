"""
OpenAI Tool Definitions（向後相容）

正式來源改由 registry 動態產生；此模組保留 export 以免舊 import 中斷。
"""
from backend.tools.registry import get_openai_tool_definitions

# 延遲屬性：首次存取時從 registry 載入
def __getattr__(name: str):
    if name == "TOOL_DEFINITIONS":
        return get_openai_tool_definitions()
    raise AttributeError(name)


# 明確 export（import * / from x import TOOL_DEFINITIONS 仍可用）
TOOL_DEFINITIONS = get_openai_tool_definitions()
