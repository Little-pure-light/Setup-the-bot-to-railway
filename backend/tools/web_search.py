"""
Web Search 工具
優先 Tavily API（可靠、適合 AI agent）；可選 DuckDuckGo 備援。
"""
from __future__ import annotations

import os
import logging
import asyncio
import re
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger("tools.web_search")

SEARCH_TIMEOUT_SECONDS = float(os.getenv("WEB_SEARCH_TIMEOUT", "12"))
DEFAULT_MAX_RESULTS = 5


def _sanitize_query(query: str) -> Optional[str]:
    q = (query or "").strip()
    if not q:
        return None
    if len(q) > 300:
        q = q[:300]
    # 阻擋明顯非搜尋用途
    if re.search(r"(?i)(file://|javascript:|data:)", q):
        return None
    return q


def _clamp_max_results(max_results: Optional[int]) -> int:
    try:
        n = int(max_results if max_results is not None else DEFAULT_MAX_RESULTS)
    except (TypeError, ValueError):
        n = DEFAULT_MAX_RESULTS
    return max(1, min(5, n))


def _format_results(answer: str, results: list, max_results: int) -> str:
    parts = []
    if answer and len(answer.strip()) > 5:
        parts.append(f"📋 摘要：{answer.strip()}")

    if results:
        parts.append("\n🔍 相關資料：")
        for i, r in enumerate(results[:max_results], 1):
            title = r.get("title", "（無標題）")
            content = (r.get("content") or r.get("snippet") or r.get("body") or "")[
                :300
            ].strip()
            url = r.get("url") or r.get("href") or ""
            # 只顯示 http(s)
            if url:
                scheme = urlparse(url).scheme.lower()
                if scheme not in ("http", "https"):
                    url = ""
            if content:
                line = f"{i}. **{title}**\n   {content}"
                if url:
                    line += f"\n   來源：{url}"
                parts.append(line)

    if not parts:
        return "[SEARCH_EMPTY] 沒有找到相關搜尋結果"
    return "\n".join(parts)


async def _search_tavily(query: str, max_results: int, api_key: str) -> str:
    try:
        from tavily import TavilyClient
    except ImportError:
        logger.error("❌ tavily-python 套件未安裝")
        return "[SEARCH_UNAVAILABLE] 搜尋套件未安裝"

    client = TavilyClient(api_key=api_key)
    loop = asyncio.get_event_loop()
    response = await asyncio.wait_for(
        loop.run_in_executor(
            None,
            lambda: client.search(
                query=query,
                search_depth="advanced",
                max_results=max_results,
                include_answer=True,
            ),
        ),
        timeout=SEARCH_TIMEOUT_SECONDS,
    )

    if not isinstance(response, dict):
        logger.warning(f"⚠️ Tavily 回傳格式非預期：{type(response)}")
        return "[SEARCH_EMPTY] 搜尋回傳格式異常"

    answer = response.get("answer", "") or ""
    results = response.get("results", []) or []
    text = _format_results(answer, results, max_results)
    logger.info(f"✅ web_search(Tavily) 完成：{query[:40]}（{len(results)} 筆）")
    return text


async def _search_duckduckgo(query: str, max_results: int) -> str:
    """
    備援：DuckDuckGo Instant Answer / HTML-less API（無 key）。
    僅作 Tavily 不可用時的降級。
    """
    import urllib.parse
    import urllib.request
    import json

    # DuckDuckGo Instant Answer API
    params = urllib.parse.urlencode(
        {
            "q": query,
            "format": "json",
            "no_html": 1,
            "skip_disambig": 1,
        }
    )
    url = f"https://api.duckduckgo.com/?{params}"

    def _fetch():
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "XiaochenguangBot/1.0"},
        )
        with urllib.request.urlopen(req, timeout=SEARCH_TIMEOUT_SECONDS) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    loop = asyncio.get_event_loop()
    data = await asyncio.wait_for(loop.run_in_executor(None, _fetch), timeout=SEARCH_TIMEOUT_SECONDS)

    answer = (data.get("AbstractText") or data.get("Answer") or "").strip()
    results = []
    for topic in (data.get("RelatedTopics") or [])[:max_results]:
        if isinstance(topic, dict) and topic.get("Text"):
            results.append(
                {
                    "title": (topic.get("Text") or "")[:80],
                    "content": topic.get("Text") or "",
                    "url": topic.get("FirstURL") or "",
                }
            )
        elif isinstance(topic, dict) and "Topics" in topic:
            for sub in topic.get("Topics") or []:
                if isinstance(sub, dict) and sub.get("Text"):
                    results.append(
                        {
                            "title": (sub.get("Text") or "")[:80],
                            "content": sub.get("Text") or "",
                            "url": sub.get("FirstURL") or "",
                        }
                    )
                if len(results) >= max_results:
                    break

    text = _format_results(answer, results, max_results)
    if text.startswith("[SEARCH_EMPTY]"):
        return "[SEARCH_EMPTY] DuckDuckGo 備援也沒有結果"
    logger.info(f"✅ web_search(DuckDuckGo) 完成：{query[:40]}")
    return "（備援搜尋）\n" + text


async def web_search(query: str, max_results: int = DEFAULT_MAX_RESULTS) -> str:
    """
    使用 Tavily API 搜尋網路；失敗時可降級 DuckDuckGo。
    錯誤一律優雅降級，不拋出到上層。
    """
    clean = _sanitize_query(query)
    if not clean:
        return "[SEARCH_INVALID] 無效的搜尋關鍵字"

    n = _clamp_max_results(max_results)
    api_key = os.getenv("TAVILY_API_KEY")
    allow_fallback = os.getenv("WEB_SEARCH_FALLBACK", "true").lower() not in (
        "0",
        "false",
        "no",
    )

    if api_key:
        try:
            return await _search_tavily(clean, n, api_key)
        except asyncio.TimeoutError:
            logger.warning(f"⏰ Tavily 逾時：{clean[:40]}")
            if not allow_fallback:
                return "[SEARCH_TIMEOUT] 搜尋逾時，請稍後再試"
        except Exception as e:
            err_msg = str(e)
            if "401" in err_msg or "unauthorized" in err_msg.lower() or "invalid api key" in err_msg.lower():
                logger.error("❌ Tavily API Key 無效")
                if not allow_fallback:
                    return "[SEARCH_AUTH_ERROR] 搜尋服務驗證失敗"
            elif "429" in err_msg or "rate limit" in err_msg.lower():
                logger.warning("⚠️ Tavily Rate Limit")
                if not allow_fallback:
                    return "[SEARCH_RATE_LIMIT] 搜尋次數已達上限，請稍後再試"
            else:
                logger.error(f"❌ Tavily 錯誤：{e}")
                if not allow_fallback:
                    return "[SEARCH_ERROR] 搜尋發生錯誤"
    else:
        logger.warning("⚠️ 未設定 TAVILY_API_KEY，嘗試備援搜尋")

    if allow_fallback:
        try:
            return await _search_duckduckgo(clean, n)
        except Exception as e:
            logger.warning(f"⚠️ 備援搜尋失敗: {e}")
            if not api_key:
                return "[SEARCH_UNAVAILABLE] 搜尋功能未啟用（缺少 TAVILY_API_KEY）"
            return "[SEARCH_ERROR] 搜尋發生錯誤，備援也失敗"

    return "[SEARCH_UNAVAILABLE] 搜尋功能未啟用"
