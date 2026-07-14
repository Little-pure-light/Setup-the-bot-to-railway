"""
OpenAI Tool Definitions
定義 AI 可以使用的工具格式（符合 OpenAI Function Calling 規格）
"""

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "當需要查詢最新資訊、新聞、時事、或你不確定自己知識是否過時時，"
                "使用此工具搜尋網路。適合用於：最新消息、即時資訊、特定事件查詢。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "要搜尋的關鍵字或問題，請用繁體中文或英文"
                    }
                },
                "required": ["query"]
            }
        }
    }
]
