"""
記憶模組（CoreController 適配層）

實際邏輯統一委派給 modules.memory_system.MemorySystem，
此處只提供模組化介面與健康檢查。
"""
from typing import Dict, Any, Optional
import os

from backend.base_module import BaseModule


class MemoryModule(BaseModule):
    """記憶模組 — 薄適配層，單一記憶系統入口"""

    def __init__(self, module_name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(module_name, config)
        self.memory_system = None

    async def load(self) -> bool:
        try:
            self.log_info("正在載入記憶模組（MemorySystem）...")
            from backend.supabase_handler import get_supabase
            from backend.openai_handler import get_openai_client
            from modules.memory_system import MemorySystem

            memories_table = os.getenv("SUPABASE_MEMORIES_TABLE", "xiaochenguang_memories")
            self.memory_system = MemorySystem(
                get_supabase(),
                get_openai_client(),
                memories_table,
            )
            self._initialized = True
            self.log_info("✅ 記憶模組載入完成（統一 MemorySystem）")
            return True
        except Exception as e:
            self.log_error(f"載入失敗: {e}")
            return False

    async def unload(self) -> bool:
        try:
            self.memory_system = None
            self._initialized = False
            return True
        except Exception as e:
            self.log_error(f"卸載失敗: {e}")
            return False

    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.memory_system:
            return {"success": False, "error": "記憶模組尚未初始化"}

        operation = data.get("operation", "store_conversation")

        try:
            if operation == "store_conversation":
                await self.memory_system.save_memory(
                    conversation_id=data.get("conversation_id", ""),
                    user_input=data.get("user_message") or data.get("user_msg", ""),
                    bot_response=data.get("assistant_message") or data.get("assistant_msg", ""),
                    emotion_analysis=data.get("emotion_analysis") or {
                        "dominant_emotion": "neutral",
                        "intensity": 0.5,
                    },
                    ai_id=data.get("ai_id", "xiaochenguang_v1"),
                    user_id=data.get("user_id"),
                    reflection=data.get("reflection"),
                )
                return {"success": True, "message": "對話已儲存"}

            if operation == "retrieve_memory":
                context = self.memory_system.get_recent_context(
                    data.get("conversation_id", "")
                )
                if context:
                    return {"success": True, "memory": context}
                history = self.memory_system.get_conversation_history(
                    data.get("conversation_id", ""), limit=5
                )
                return {"success": bool(history), "memory": history or None}

            if operation == "recall":
                recalled = await self.memory_system.recall_memories(
                    user_message=data.get("user_message", ""),
                    conversation_id=data.get("conversation_id", ""),
                    user_id=data.get("user_id", "default_user"),
                )
                return {"success": True, "recalled": recalled}

            return {"success": False, "error": f"未知操作: {operation}"}
        except Exception as e:
            self.log_error(f"處理失敗: {e}")
            return {"success": False, "error": str(e)}

    async def health_check(self) -> Dict[str, Any]:
        base = await super().health_check() if hasattr(super(), "health_check") else {}
        return {
            **(base if isinstance(base, dict) else {}),
            "status": "healthy" if self._initialized and self.memory_system else "unhealthy",
            "backend": "MemorySystem",
            "redis": bool(self.memory_system and self.memory_system.redis),
        }
