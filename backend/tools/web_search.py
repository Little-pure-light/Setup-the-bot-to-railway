"""
Web Search 工具
使用 Tavily API 進行網路搜尋
"""
import os
import logging
import asyncio
from typing import Optional

logger = logging.getLogger("tools.web_search")

SEARCH_TIMEOUT_SECONDS = 10  # 搜尋逾時設定


async def web_search(query: str, max_results: int = 3) -> str:
    """
    使用 Tavily API 搜尋網路，回傳格式化的搜尋結果字串。
    所有錯誤都會優雅降級，不會讓上層崩潰。

    參數:
        query: 搜尋關鍵字
        max_results: 最多回傳幾筆結果（預設 3）

    回傳:
        搜尋結果的純文字摘要，若失敗則回傳降級訊息
    """
    api_key = os.getenv("TAVILY_API_KEY")

    if not api_key:
        logger.warning("⚠️ 未設定 TAVILY_API_KEY，web_search 跳過")
        return "[SEARCH_UNAVAILABLE] 搜尋功能未啟用"

    try:
        from tavily import TavilyClient
    except ImportError:
        logger.error("❌ tavily-python 套件未安裝")
        return "[SEARCH_UNAVAILABLE] 搜尋套件未安裝"

    try:
        client = TavilyClient(api_key=api_key)

        # 用 asyncio 跑同步 API + timeout 保護
        loop = asyncio.get_event_loop()
        response = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: client.search(
                query=query,
                search_depth="basic",
                max_results=max_results,
                include_answer=True
            )),
            timeout=SEARCH_TIMEOUT_SECONDS
        )

        # 檢查回傳格式
        if not isinstance(response, dict):
            logger.warning(f"⚠️ Tavily 回傳格式非預期：{type(response)}")
            return "[SEARCH_EMPTY] 搜尋回傳格式異常"

        parts = []

        # AI 摘要答案
        answer = response.get("answer", "")
        if answer and len(answer.strip()) > 5:
            parts.append(f"📋 摘要：{answer.strip()}")

        # 各筆來源
        results = response.get("results", [])
        if results:
            parts.append("\n🔍 相關資料：")
            for i, r in enumerate(results[:max_results], 1):
                title = r.get("title", "（無標題）")
                content = r.get("content", "")[:300].strip()
                url = r.get("url", "")
                if content:
                    parts.append(f"{i}. **{title}**\n   {content}\n   來源：{url}")

        if not parts:
            logger.info(f"ℹ️ web_search 查詢無結果：{query}")
            return "[SEARCH_EMPTY] 沒有找到相關搜尋結果"

        result_text = "\n".join(parts)
        logger.info(f"✅ web_search 完成：{query}（{len(results)} 筆）")
        return result_text

    except asyncio.TimeoutError:
        logger.warning(f"⏰ web_search 逾時（{SEARCH_TIMEOUT_SECONDS}秒）：{query}")
        return "[SEARCH_TIMEOUT] 搜尋逾時，請稍後再試"

    except Exception as e:
        err_msg = str(e)
        # 判斷常見錯誤類型
        if "401" in err_msg or "unauthorized" in err_msg.lower() or "invalid api key" in err_msg.lower():
            logger.error("❌ Tavily API Key 無效")
            return "[SEARCH_AUTH_ERROR] 搜尋服務驗證失敗"
        elif "429" in err_msg or "rate limit" in err_msg.lower():
            logger.warning("⚠️ Tavily Rate Limit 超限")
            return "[SEARCH_RATE_LIMIT] 搜尋次數已達上限，請稍後再試"
        elif "connect" in err_msg.lower() or "network" in err_msg.lower() or "connection" in err_msg.lower():
            logger.warning(f"⚠️ web_search 網路連線失敗：{e}")
            return "[SEARCH_NETWORK_ERROR] 網路連線失敗，無法搜尋"
        else:
            logger.error(f"❌ web_search 未知錯誤：{e}")
            return f"[SEARCH_ERROR] 搜尋發生錯誤"

