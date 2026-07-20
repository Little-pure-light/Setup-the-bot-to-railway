"""
OpenAI Model Gateway — SDK 僅在此層使用。
Kernel 其餘部分只看 dict 結果。
"""
from __future__ import annotations

from typing import Any, AsyncIterator, Dict, List, Optional

from backend.ai_kernel.errors import ModelGatewayError, ModelTimeoutError


class OpenAIModelGateway:
    """
    包裝既有 backend.openai_handler 函式，隔離 SDK。
    可注入 mock complete/stream 以供測試。
    """

    def __init__(
        self,
        *,
        complete_fn=None,
        complete_tools_fn=None,
        stream_fn=None,
    ):
        self._complete_fn = complete_fn
        self._complete_tools_fn = complete_tools_fn
        self._stream_fn = stream_fn

    def _ensure_fns(self):
        if self._complete_fn is None:
            from backend.openai_handler import (
                generate_response,
                generate_response_stream,
                generate_response_with_tools,
                get_openai_client,
            )

            client = get_openai_client()

            async def _complete(messages, *, model, temperature, max_tokens):
                return await generate_response(
                    client,
                    messages,
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    return_usage=True,
                )

            self._complete_fn = _complete
            self._complete_tools_fn = generate_response_with_tools
            self._stream_fn = generate_response_stream

    async def complete(
        self,
        messages: List[Dict[str, Any]],
        *,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> Dict[str, Any]:
        self._ensure_fns()
        try:
            result = await self._complete_fn(
                messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if isinstance(result, str):
                return {
                    "content": result,
                    "usage": {},
                    "model": model,
                }
            return result
        except TimeoutError as e:
            raise ModelTimeoutError(str(e)) from e
        except Exception as e:
            msg = str(e).lower()
            if "timeout" in msg or "timed out" in msg:
                raise ModelTimeoutError(str(e)) from e
            raise ModelGatewayError(type(e).__name__) from e

    async def complete_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        *,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> Dict[str, Any]:
        self._ensure_fns()
        try:
            return await self._complete_tools_fn(
                messages,
                tools=tools,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except TimeoutError as e:
            raise ModelTimeoutError(str(e)) from e
        except Exception as e:
            msg = str(e).lower()
            if "timeout" in msg:
                raise ModelTimeoutError(str(e)) from e
            raise ModelGatewayError(type(e).__name__) from e

    async def stream(
        self,
        messages: List[Dict[str, Any]],
        *,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> AsyncIterator[Dict[str, Any]]:
        self._ensure_fns()
        try:
            async for event in self._stream_fn(
                messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            ):
                if isinstance(event, dict):
                    yield event
                else:
                    yield {"type": "content", "text": str(event)}
        except TimeoutError as e:
            raise ModelTimeoutError(str(e)) from e
        except Exception as e:
            raise ModelGatewayError(type(e).__name__) from e
