"""OpenAI 假客戶端與回應（單元/整合測試用）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class FakeUsage:
    prompt_tokens: int = 10
    completion_tokens: int = 20
    total_tokens: int = 30


@dataclass
class FakeMessage:
    content: str = "這是測試回覆"
    tool_calls: Optional[list] = None


@dataclass
class FakeChoice:
    message: FakeMessage = field(default_factory=FakeMessage)
    finish_reason: str = "stop"
    delta: Optional[Any] = None


@dataclass
class FakeChatResponse:
    choices: List[FakeChoice] = field(default_factory=lambda: [FakeChoice()])
    usage: FakeUsage = field(default_factory=FakeUsage)


class FakeOpenAIClient:
    """同步假 OpenAI client。"""

    def __init__(self, reply: str = "這是測試回覆", raise_error: Optional[Exception] = None):
        self.reply = reply
        self.raise_error = raise_error
        self.calls: List[Dict[str, Any]] = []
        self.embeddings = FakeEmbeddings()
        self.chat = FakeChat(self)

    def reset(self):
        self.calls.clear()
        self.embeddings.calls.clear()


class FakeChat:
    def __init__(self, parent: FakeOpenAIClient):
        self._parent = parent
        self.completions = self

    def create(self, **kwargs):
        self._parent.calls.append(kwargs)
        if self._parent.raise_error:
            raise self._parent.raise_error
        return FakeChatResponse(
            choices=[FakeChoice(message=FakeMessage(content=self._parent.reply))]
        )


class FakeEmbeddings:
    def __init__(self, dim: int = 8):
        self.dim = dim
        self.calls: List[Dict[str, Any]] = []
        self.raise_error: Optional[Exception] = None

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.raise_error:
            raise self.raise_error

        class _Data:
            def __init__(self, embedding):
                self.embedding = embedding

        class _Resp:
            def __init__(self, embedding):
                self.data = [_Data(embedding)]

        # 固定假向量（長度可縮短供測試，正式 API 為 1536）
        text = kwargs.get("input") or ""
        seed = float(len(str(text)) % 97) / 97.0
        embedding = [seed + i * 0.001 for i in range(self.dim)]
        return _Resp(embedding)
