"""
外部依賴介面（Port）— Kernel 只依賴這些抽象，由 Adapter 注入。
"""
from __future__ import annotations

from typing import Any, AsyncIterator, Dict, List, Optional, Protocol


class MemoryPort(Protocol):
    async def recall(self, user_message: str, conversation_id: str, user_id: str) -> str: ...

    def history(self, conversation_id: str, limit: int = 5) -> str: ...

    async def save(
        self,
        conversation_id: str,
        user_input: str,
        bot_response: str,
        emotion_analysis: dict,
        *,
        ai_id: str,
        user_id: Optional[str],
    ) -> None: ...


class FileContextPort(Protocol):
    def get_file_content(self, conversation_id: str) -> str: ...


class PromptPort(Protocol):
    async def build(
        self,
        user_message: str,
        recalled_memories: str,
        conversation_history: str,
        file_content: str,
    ) -> tuple[list, dict]: ...


class ModerationPort(Protocol):
    async def check(self, text: str) -> dict: ...


class BudgetPort(Protocol):
    def check(self, user_id: str) -> tuple[bool, str, dict]: ...

    def record(
        self,
        *,
        user_id: str,
        conversation_id: str,
        model: str,
        usage: dict,
        endpoint: str,
        meta: Optional[dict] = None,
    ) -> dict: ...


class ModelGatewayPort(Protocol):
    async def complete(
        self,
        messages: List[Dict[str, Any]],
        *,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> Dict[str, Any]: ...

    async def complete_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        *,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> Dict[str, Any]: ...

    def stream(
        self,
        messages: List[Dict[str, Any]],
        *,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> AsyncIterator[Dict[str, Any]]: ...


class ToolExecutorPort(Protocol):
    def openai_definitions(self) -> List[Dict[str, Any]]: ...

    async def execute_calls(
        self,
        tool_calls: list,
        *,
        context: Optional[Dict[str, Any]] = None,
        max_calls: int = 5,
    ) -> List[Dict[str, Any]]: ...


class VoiceHintPort(Protocol):
    def build_hint(self, *, voice_mode: bool, car_mode: bool) -> str: ...


class SpeechSanitizePort(Protocol):
    def sanitize(self, text: str) -> str: ...


class PostProcessPort(Protocol):
    async def run_jobs(self, jobs: list) -> None: ...


class KernelDeps:
    """注入集合。"""

    def __init__(
        self,
        *,
        memory: MemoryPort,
        files: FileContextPort,
        prompt: PromptPort,
        moderation: ModerationPort,
        budget: BudgetPort,
        model: ModelGatewayPort,
        tools: ToolExecutorPort,
        voice: VoiceHintPort,
        speech: SpeechSanitizePort,
        post_process: Optional[PostProcessPort] = None,
    ):
        self.memory = memory
        self.files = files
        self.prompt = prompt
        self.moderation = moderation
        self.budget = budget
        self.model = model
        self.tools = tools
        self.voice = voice
        self.speech = speech
        self.post_process = post_process
