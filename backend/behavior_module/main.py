"""
行為調節模組 - Behavior Module
根據反思結果調整人格與行為策略
"""
from typing import Dict, Any, Optional
from backend.base_module import BaseModule


class BehaviorModule(BaseModule):
    """行為調節模組類別"""
    
    def __init__(self, module_name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(module_name, config)
        self.adjustment_rate = self.config.get("settings", {}).get("personality_adjustment_rate", 0.01)
        self.personality_vector = {
            "empathy": 0.5,
            "curiosity": 0.5,
            "humor": 0.5,
            "technical_depth": 0.5
        }
    
    async def load(self) -> bool:
        """載入模組"""
        try:
            self.log_info("正在載入行為調節模組...")
            self._initialized = True
            self.log_info("✅ 行為調節模組載入完成")
            return True
        except Exception as e:
            self.log_error(f"載入失敗: {e}")
            return False
    
    async def unload(self) -> bool:
        """卸載模組"""
        try:
            self.log_info("正在卸載行為調節模組...")
            self._initialized = False
            return True
        except Exception as e:
            self.log_error(f"卸載失敗: {e}")
            return False
    
    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        處理行為調節
        
        根據反思結果調整人格向量
        """
        try:
            reflection = data.get("reflection", {})
            emotion_analysis = data.get("emotion_analysis", {})
            
            # 根據反思調整人格
            adjustments = await self._calculate_adjustments(reflection, emotion_analysis)
            
            # 應用調整
            await self._apply_adjustments(adjustments)
            
            return {
                "success": True,
                "personality_vector": self.personality_vector,
                "adjustments": adjustments
            }
            
        except Exception as e:
            self.log_error(f"行為調節失敗: {e}")
            return {"success": False, "error": str(e)}
    
    async def _calculate_adjustments(
        self,
        reflection: Dict[str, Any],
        emotion_analysis: Dict[str, Any]
    ) -> Dict[str, float]:
        """計算人格向量調整值"""
        adjustments = {}
        
        # 根據情感分析調整
        if emotion_analysis:
            emotion = emotion_analysis.get("dominant_emotion", "neutral")
            if emotion in ["sadness", "fear"]:
                adjustments["empathy"] = self.adjustment_rate
            elif emotion == "joy":
                adjustments["humor"] = self.adjustment_rate
        
        # 根據反思結果調整
        if reflection.get("causes"):
            if "缺少實例" in str(reflection.get("causes")):
                adjustments["technical_depth"] = self.adjustment_rate
        
        return adjustments
    
    async def _apply_adjustments(self, adjustments: Dict[str, float]):
        """應用人格向量調整"""
        for trait, adjustment in adjustments.items():
            if trait in self.personality_vector:
                new_value = self.personality_vector[trait] + adjustment
                # 限制在 [0, 1] 範圍內
                self.personality_vector[trait] = max(0.0, min(1.0, new_value))
