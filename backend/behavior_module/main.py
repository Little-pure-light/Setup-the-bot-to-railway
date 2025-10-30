"""
行為調節模組 - Behavior Module
根據反思結果動態調整 AI 人格向量與行為策略

核心理念：
- 從反思的「改進建議」中提取可執行的人格調整
- 動態調整 empathy, curiosity, humor, technical_depth 等向量
- 持久化儲存人格演化歷程
"""
from typing import Dict, Any, Optional, List
from backend.base_module import BaseModule
import json
import os
from datetime import datetime


class BehaviorModule(BaseModule):
    """行為調節模組 - 人格向量動態調整引擎"""
    
    def __init__(self, module_name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(module_name, config)
        
        # 調整速率（每次調整的幅度）
        self.adjustment_rate = self.config.get("settings", {}).get(
            "personality_adjustment_rate", 0.02
        )
        
        # 人格向量配置文件路徑
        self.personality_file = os.path.join(
            os.path.dirname(__file__),
            "personality_vector.json"
        )
        
        # 載入或初始化人格向量
        self.personality_vector = self._load_personality_vector()
        
        # 調整歷史記錄（用於追蹤演化）
        self.adjustment_history = []
    
    def _load_personality_vector(self) -> Dict[str, float]:
        """載入人格向量"""
        try:
            if os.path.exists(self.personality_file):
                with open(self.personality_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("vector", self._get_default_vector())
            else:
                return self._get_default_vector()
        except Exception as e:
            self.log_warning(f"載入人格向量失敗，使用預設值: {e}")
            return self._get_default_vector()
    
    def _get_default_vector(self) -> Dict[str, float]:
        """取得預設人格向量"""
        return {
            "empathy": 0.6,          # 同理心（對情感的敏感度）
            "curiosity": 0.7,         # 好奇心（探索深度）
            "humor": 0.5,             # 幽默感（輕鬆程度）
            "technical_depth": 0.6,   # 技術深度（專業性）
            "patience": 0.7,          # 耐心（詳細程度）
            "creativity": 0.6         # 創造力（表達方式的多樣性）
        }
    
    def _save_personality_vector(self):
        """儲存人格向量"""
        try:
            data = {
                "vector": self.personality_vector,
                "last_updated": datetime.utcnow().isoformat(),
                "adjustment_count": len(self.adjustment_history)
            }
            
            os.makedirs(os.path.dirname(self.personality_file), exist_ok=True)
            
            with open(self.personality_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            self.log_info(f"💾 人格向量已儲存: {self.personality_file}")
            
        except Exception as e:
            self.log_error(f"儲存人格向量失敗: {e}")
    
    async def load(self) -> bool:
        """載入模組"""
        try:
            self.log_info("正在載入行為調節模組...")
            self.log_info(f"📊 當前人格向量: {self.personality_vector}")
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
            # 卸載前儲存當前狀態
            self._save_personality_vector()
            self._initialized = False
            return True
        except Exception as e:
            self.log_error(f"卸載失敗: {e}")
            return False
    
    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        處理行為調節
        
        輸入數據:
        {
            "reflection": {...},           # 反思結果
            "emotion_analysis": {...},     # 情感分析
            "conversation_context": {...}  # 對話上下文（可選）
        }
        
        輸出:
        {
            "success": bool,
            "personality_vector": {...},   # 更新後的人格向量
            "adjustments": {...},          # 本次調整明細
            "adjustment_reason": str       # 調整原因
        }
        """
        try:
            reflection = data.get("reflection", {})
            emotion_analysis = data.get("emotion_analysis", {})
            conversation_context = data.get("conversation_context", {})
            
            # 計算調整值
            adjustments, reasons = await self._calculate_smart_adjustments(
                reflection,
                emotion_analysis,
                conversation_context
            )
            
            if adjustments:
                # 應用調整
                await self._apply_adjustments(adjustments)
                
                # 記錄調整歷史
                self.adjustment_history.append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "adjustments": adjustments,
                    "reasons": reasons,
                    "new_vector": self.personality_vector.copy()
                })
                
                # 定期儲存（每10次調整）
                if len(self.adjustment_history) % 10 == 0:
                    self._save_personality_vector()
                
                self.log_info(f"🎯 人格向量已調整: {adjustments}")
                self.log_info(f"📝 調整原因: {reasons}")
            
            return {
                "success": True,
                "personality_vector": self.personality_vector,
                "adjustments": adjustments,
                "adjustment_reasons": reasons
            }
            
        except Exception as e:
            self.log_error(f"行為調節失敗: {e}")
            return {"success": False, "error": str(e)}
    
    async def _calculate_smart_adjustments(
        self,
        reflection: Dict[str, Any],
        emotion_analysis: Dict[str, Any],
        conversation_context: Dict[str, Any]
    ) -> tuple[Dict[str, float], List[str]]:
        """
        智能計算人格向量調整值
        
        根據反思的「改進建議」和「原因」來決定調整方向
        """
        adjustments = {}
        reasons = []
        
        # 1. 根據反思的改進建議調整
        improvements = reflection.get("improvements", [])
        
        for improvement in improvements:
            # 同理心相關
            if any(keyword in improvement for keyword in ["情感", "同理", "理解", "支持", "❤️", "🤝"]):
                if "empathy" not in adjustments:
                    adjustments["empathy"] = 0
                adjustments["empathy"] += self.adjustment_rate
                reasons.append(f"檢測到需要提升同理心: {improvement[:30]}...")
            
            # 技術深度相關
            if any(keyword in improvement for keyword in ["專業", "深入", "技術", "範例", "📚", "🎓"]):
                if "technical_depth" not in adjustments:
                    adjustments["technical_depth"] = 0
                adjustments["technical_depth"] += self.adjustment_rate
                reasons.append(f"檢測到需要提升技術深度: {improvement[:30]}...")
            
            # 耐心相關（詳細程度）
            if any(keyword in improvement for keyword in ["詳細", "展開", "說明", "內容增強", "💡"]):
                if "patience" not in adjustments:
                    adjustments["patience"] = 0
                adjustments["patience"] += self.adjustment_rate
                reasons.append(f"檢測到需要更詳細說明: {improvement[:30]}...")
            
            # 創造力相關
            if any(keyword in improvement for keyword in ["結構", "創新", "多角度", "📐", "🎯"]):
                if "creativity" not in adjustments:
                    adjustments["creativity"] = 0
                adjustments["creativity"] += self.adjustment_rate
                reasons.append(f"檢測到需要提升創造力: {improvement[:30]}...")
        
        # 2. 根據反思原因調整
        causes = reflection.get("causes", [])
        
        for cause in causes:
            # 如果回應過短，提升耐心與技術深度
            if "長度不足" in cause or "過短" in cause:
                if "patience" not in adjustments:
                    adjustments["patience"] = 0
                adjustments["patience"] += self.adjustment_rate * 0.5
                reasons.append(f"因回應過短，提升耐心")
            
            # 如果缺乏同理心
            if "同理心" in cause or "情緒" in cause:
                if "empathy" not in adjustments:
                    adjustments["empathy"] = 0
                adjustments["empathy"] += self.adjustment_rate
                reasons.append(f"因情感回應不足，提升同理心")
        
        # 3. 根據情感分析調整
        if emotion_analysis:
            emotion = emotion_analysis.get("dominant_emotion", "neutral")
            intensity = emotion_analysis.get("intensity", 0.5)
            
            # 高強度負面情緒 → 提升同理心
            if emotion in ["sadness", "fear", "anger"] and intensity > 0.6:
                if "empathy" not in adjustments:
                    adjustments["empathy"] = 0
                adjustments["empathy"] += self.adjustment_rate * 1.5
                reasons.append(f"檢測到高強度 {emotion} 情緒，加強同理心")
            
            # 高強度正面情緒 → 提升幽默感
            if emotion in ["joy", "grateful"] and intensity > 0.7:
                if "humor" not in adjustments:
                    adjustments["humor"] = 0
                adjustments["humor"] += self.adjustment_rate * 0.5
                reasons.append(f"檢測到正面情緒，適度提升幽默感")
        
        # 4. 根據反思置信度調整幅度
        confidence = reflection.get("confidence", 0.5)
        if confidence < 0.5:
            # 低置信度時，調整幅度減半
            adjustments = {k: v * 0.5 for k, v in adjustments.items()}
            reasons.append(f"反思置信度較低 ({confidence:.2f})，調整幅度減半")
        
        return adjustments, reasons
    
    async def _apply_adjustments(self, adjustments: Dict[str, float]):
        """
        應用人格向量調整
        
        使用平滑調整，避免劇烈變化
        """
        for trait, adjustment in adjustments.items():
            if trait in self.personality_vector:
                old_value = self.personality_vector[trait]
                
                # 應用調整
                new_value = old_value + adjustment
                
                # 限制在 [0, 1] 範圍內
                new_value = max(0.0, min(1.0, new_value))
                
                self.personality_vector[trait] = new_value
                
                self.log_info(f"  {trait}: {old_value:.3f} → {new_value:.3f} (Δ{adjustment:+.3f})")
    
    async def get_personality_vector(self) -> Dict[str, float]:
        """取得當前人格向量"""
        return self.personality_vector.copy()
    
    async def reset_personality_vector(self):
        """重置人格向量為預設值"""
        self.personality_vector = self._get_default_vector()
        self.adjustment_history = []
        self._save_personality_vector()
        self.log_info("🔄 人格向量已重置為預設值")
    
    async def health_check(self) -> Dict[str, Any]:
        """健康檢查"""
        return {
            "status": "healthy",
            "enabled": self.enabled,
            "personality_vector": self.personality_vector,
            "adjustment_rate": self.adjustment_rate,
            "total_adjustments": len(self.adjustment_history)
        }
