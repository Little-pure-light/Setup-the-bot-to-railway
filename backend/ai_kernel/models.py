"""
Kernel 核心資料模型（Pydantic）— 不依賴 FastAPI Request / OpenAI SDK。
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class PlanAction(str, Enum):
    DIRECT_ANSWER = "direct_answer"
    USE_TOOLS = "use_tools"
    SHORT_VOICE = "short_voice"


class KernelRequest(BaseModel):
    """進入 Kernel 的標準請求（由 Router 轉換，非 FastAPI Request）。"""

    user_message: str
    conversation_id: str
    user_id: str = "default_user"
    ai_id: str = "xiaochenguang_v1"
    voice_mode: bool = False
    car_mode: bool = False
    input_method: str = "text"
    speak_response: bool = False
    use_tools: bool = True
    stream: bool = True
    request_id: str = ""
    shadow: bool = False  # shadow 模式禁止副作用


class ModelConfig(BaseModel):
    model: str = "gpt-4o-mini"
    temperature: float = 0.8
    max_tokens: int = 2000


class ResponseStrategy(BaseModel):
    name: str = "default"
    max_tokens: int = 2000
    temperature: float = 0.8
    voice_friendly: bool = False
    car_mode: bool = False
    system_hint: str = ""


class PlanStep(BaseModel):
    action: str = "answer"
    tool_name: Optional[str] = None
    rationale: str = ""


class Plan(BaseModel):
    action: PlanAction = PlanAction.DIRECT_ANSWER
    steps: List[PlanStep] = Field(default_factory=list)
    allow_tools: bool = False
    reason: str = "default"


class ContextBlock(BaseModel):
    """Context 片段；priority 越高越不易被裁剪。"""

    key: str
    role: Literal["system", "user", "assistant"] = "system"
    content: str
    priority: int = 50  # 100=safety, 90=user_msg, 10=optional memory
    estimated_tokens: int = 0
    required: bool = False


class KernelContext(BaseModel):
    request: KernelRequest
    blocks: List[ContextBlock] = Field(default_factory=list)
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    emotion_analysis: Dict[str, Any] = Field(default_factory=dict)
    recalled_memories: str = ""
    conversation_history: str = ""
    file_content: str = ""
    plan: Optional[Plan] = None
    model_config_obj: ModelConfig = Field(default_factory=ModelConfig)
    strategy: ResponseStrategy = Field(default_factory=ResponseStrategy)
    tools_used: List[Dict[str, Any]] = Field(default_factory=list)
    usage: Dict[str, Any] = Field(default_factory=dict)
    meta: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"protected_namespaces": ()}


class KernelEvent(BaseModel):
    """可串流給前端的內部事件（再由 Router 轉成 __XCG_* 協議）。"""

    type: Literal["content", "tool_status", "usage", "error", "trace"] = "content"
    text: str = ""
    status: str = ""
    data: Dict[str, Any] = Field(default_factory=dict)


class PostProcessJob(BaseModel):
    request_id: str
    operation: str = "save_memory"  # save_memory | reflection | personality
    conversation_id: str
    user_id: str
    user_message: str
    assistant_message: str
    emotion_analysis: Dict[str, Any] = Field(default_factory=dict)
    ai_id: str = "xiaochenguang_v1"
    skip_side_effects: bool = False


class KernelResult(BaseModel):
    assistant_message: str = ""
    emotion_analysis: Dict[str, Any] = Field(default_factory=dict)
    conversation_id: str = ""
    usage: Dict[str, Any] = Field(default_factory=dict)
    tools_used: List[Dict[str, Any]] = Field(default_factory=list)
    speech_text: Optional[str] = None
    events: List[KernelEvent] = Field(default_factory=list)
    plan: Optional[Plan] = None
    post_process_jobs: List[PostProcessJob] = Field(default_factory=list)
    used_kernel: bool = True
    fell_back_to_legacy: bool = False
    error: Optional[str] = None
    blocked: bool = False
    trace_id: str = ""
