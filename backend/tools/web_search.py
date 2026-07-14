"""
Web Search 工具
使用 Tavily API 進行網路搜尋
"""
import os
import logging
from typing import Optional

logger = logging.getLogger("tools.web_search")


async def web_search(query: str, max_results: int = 3) -> str:
    """
    使用 Tavily API 搜尋網路，回傳格式化的搜尋結果字串。

    參數:
        query: 搜尋關鍵字
        max_results: 最多回傳幾筆結果（預設 3）

    回傳:
        搜尋結果的純文字摘要，若失敗則回傳錯誤說明
    """
    api_key = os.getenv("TAVILY_API_KEY")

    if not api_key:
        logger.warning("⚠️ 未設定 TAVILY_API_KEY，web_search 無法使用")
        return "（搜尋功能目前無法使用，請直接根據既有知識回答）"

    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=api_key)

        response = client.search(
            query=query,
            search_depth="basic",
            max_results=max_results,
            include_answer=True
        )

        # 整理結果
        parts = []

        # 如果有 AI 摘要答案，優先放入
        if response.get("answer"):
            parts.append(f"📋 摘要：{response['answer']}")

        # 加入各筆來源
        results = response.get("results", [])
        if results:
            parts.append("\n🔍 相關資料：")
            for i, r in enumerate(results[:max_results], 1):
                title = r.get("title", "")
                content = r.get("content", "")[:300]
                url = r.get("url", "")
                parts.append(f"{i}. **{title}**\n   {content}\n   來源：{url}")

        if not parts:
            return "搜尋完成但沒有找到相關結果。"

        result_text = "\n".join(parts)
        logger.info(f"✅ web_search 完成，查詢：{query}，結果數：{len(results)}")
        return result_text

    except ImportError:
        logger.error("❌ tavily 套件未安裝，請執行 pip install tavily-python")
        return "（搜尋功能目前無法使用：缺少 tavily 套件）"
    except Exception as e:
        logger.error(f"❌ web_search 失敗：{e}")
        return f"（搜尋時發生錯誤，請直接根據既有知識回答。錯誤：{str(e)[:100]}）"
