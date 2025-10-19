"""
反思模組 - Reflection Module
負責自我反思、因果分析與改進建議生成
"""
from typing import Dict, Any, Optional
from backend.base_module import BaseModule
import json


class ReflectionModule(BaseModule):
    """反思模組類別"""
    
    def __init__(self, module_name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(module_name, config)
        self.reflection_template = self.config.get("settings", {}).get(
            "reflection_prompt_template", "反推果因法則"
        )
    
    async def load(self) -> bool:
        """載入模組"""
        try:
            self.log_info("正在載入反思模組...")
            self._initialized = True
            self.log_info("✅ 反思模組載入完成")
            return True
        except Exception as e:
            self.log_error(f"載入失敗: {e}")
            return False
    
    async def unload(self) -> bool:
        """卸載模組"""
        try:
            self.log_info("正在卸載反思模組...")
            self._initialized = False
            return True
        except Exception as e:
            self.log_error(f"卸載失敗: {e}")
            return False
    
    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        執行反思分析
        
        輸入數據格式:
        {
            "user_message": str,
            "assistant_message": str,
            "emotion_analysis": dict
        }
        
        輸出格式:
        {
            "reflection_summary": str,
            "causes": List[str],
            "improvement_suggestions": List[str]
        }
        """
        try:
            user_message = data.get("user_message", "")
            assistant_message = data.get("assistant_message", "")
            emotion_analysis = data.get("emotion_analysis", {})
            
            # 執行反思分析
            reflection_result = await self._analyze_response(
                user_message,
                assistant_message,
                emotion_analysis
            )
            
            return {
                "success": True,
                "reflection": reflection_result
            }
            
        except Exception as e:
            self.log_error(f"反思處理失敗: {e}")
            return {"success": False, "error": str(e)}
    
    async def _analyze_response(
        self,
        user_message: str,
        assistant_message: str,
        emotion_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """分析回應並生成反思結果"""
        
        # 基本反思邏輯
        reflection = {
            "summary": "",
            "causes": [],
            "improvement_suggestions": [],
            "confidence": 0.8
        }
        
        # 分析回應長度
        response_length = len(assistant_message)
        if response_length < 20:
            reflection["summary"] = "回應過短，需要更詳細的說明"
            reflection["causes"].append("回應內容不足")
            reflection["improvement_suggestions"].append("增加具體例子和細節")
        elif response_length > 500:
            reflection["summary"] = "回應較長，資訊豐富"
            reflection["causes"].append("提供了充分的說明")
        else:
            reflection["summary"] = "回應適中，內容平衡"
        
        # 分析情感匹配度
        if emotion_analysis:
            dominant_emotion = emotion_analysis.get("dominant_emotion", "neutral")
            if dominant_emotion in ["sadness", "fear", "anger"]:
                reflection["causes"].append("使用者可能需要更多同理心回應")
                reflection["improvement_suggestions"].append("增強情感支持語句")
        
        return reflection
