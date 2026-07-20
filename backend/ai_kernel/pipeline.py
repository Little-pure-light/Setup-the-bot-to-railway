"""Request Pipeline — 有序 stages。"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from backend.ai_kernel.tracing import KernelTrace


class PipelineStage:
    def __init__(self, name: str, handler: Callable):
        self.name = name
        self.handler = handler  # async (state) -> state


class RequestPipeline:
    def __init__(self, stages: Optional[List[PipelineStage]] = None, trace: Optional[KernelTrace] = None):
        self.stages = list(stages or [])
        self.trace = trace

    def add(self, name: str, handler: Callable) -> "RequestPipeline":
        self.stages.append(PipelineStage(name, handler))
        return self

    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        for stage in self.stages:
            if self.trace:
                self.trace.start(stage.name)
            try:
                state = await stage.handler(state)
                if self.trace:
                    self.trace.end(stage.name, status="ok")
            except Exception as e:
                if self.trace:
                    self.trace.end(
                        stage.name,
                        status="error",
                        error_code=type(e).__name__,
                    )
                raise
        return state
