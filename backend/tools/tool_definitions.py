"""
OpenAI Tool Definitions
定義 AI 可以使用的工具格式（符合 OpenAI Function Calling 規格）
"""
import datetime

# 取得目前年份，對 AI 提示目前時間
_CURRENT_YEAR = datetime.datetime.now().year

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                f"當需要查詢最新資訊、新聞、時事、或你不確定自己知識是否過時時，"
                f"使用此工具搜尋網路。適合用於：最新消息、即時資訊、特定事件查詢。"
                f"目前年份為 {_CURRENT_YEAR} 年。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            f"要搜尋的關鍵字或問題。"
                            f"建議用英文搜尋，效果更好。"
                            f"若用戶問的是最新資訊，請在查詢詞加上年份（如 {_CURRENT_YEAR}）以獲得最新結果。"
                        )
                    }
                },
                "required": ["query"]
            }
        }
    }
]
