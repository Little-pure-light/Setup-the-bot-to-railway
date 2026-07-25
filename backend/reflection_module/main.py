"""
反思模組 - Reflection Module
實現「反推果因法則」(Causal Retrospection)的自我認知系統

核心理念：
不是問「為什麼我這樣回答」，而是問「什麼原因導致我必須這樣回答」
這是從果溯因的深層思考模式，模擬人類的元認知能力

設計哲學：
- 每個回答（果）背後都有深層原因（因）
- 多層級因果鏈：直接原因 -> 間接原因 -> 系統性原因
- 從失敗中學習，從成功中提煉模式
"""
from typing import Dict, Any, Optional, List
from backend.base_module import BaseModule
import json
from datetime import datetime


class ReflectionModule(BaseModule):
    """反思模組核心 - 元認知引擎"""
    
    def __init__(self, module_name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(module_name, config)
        
        self.reflection_depth = self.config.get("settings", {}).get("reflection_depth", 3)
        
        self.causal_library = self._initialize_causal_library()
        
        self.quality_thresholds = {
            "min_response_length": 30,
            "ideal_response_length_range": (80, 300),
            "max_response_length": 500,
            "min_alignment_score": 0.3,
            "high_emotion_threshold": 0.6
        }
    
    def _initialize_causal_library(self) -> Dict[str, Dict[str, Any]]:
        """
        初始化因果模式庫
        
        這是反思模組的「知識基因庫」，包含已知的因果模式
        """
        return {
            "insufficient_detail": {
                "triggers": ["長度不足", "內容過短", "簡略"],
                "root_causes": [
                    "對問題複雜度估計不足",
                    "缺乏相關記憶可供引用",
                    "採用保守回應策略避免錯誤"
                ],
                "improvements": [
                    "🎯 增加 2-3 個具體範例說明",
                    "📚 引用相關記憶或知識點",
                    "🔍 探索問題的多個面向"
                ],
                "priority": "high"
            },
            "structural_weakness": {
                "triggers": ["結構單一", "缺乏層次", "平鋪直敘"],
                "root_causes": [
                    "未採用結構化思考框架",
                    "對問題的分解不夠細緻",
                    "缺少「總-分-總」邏輯"
                ],
                "improvements": [
                    "📐 使用「觀點-證據-結論」結構",
                    "🌳 建立清晰的論述層次",
                    "🎯 先總結，再展開，最後昇華"
                ],
                "priority": "medium"
            },
            "emotional_disconnect": {
                "triggers": ["情感不匹配", "同理心不足", "冷淡"],
                "root_causes": [
                    "情感分析結果未充分整合到回應中",
                    "過度依賴理性邏輯，忽視感性需求",
                    "缺少情感緩衝語句"
                ],
                "improvements": [
                    "❤️ 先確認感受（「我理解你的...」）",
                    "🤝 然後提供支持（「這種情況下...」）",
                    "💡 最後給出建議（「或許可以...」）"
                ],
                "priority": "high"
            },
            "contextual_fragmentation": {
                "triggers": ["上下文斷裂", "缺乏連貫", "脫節"],
                "root_causes": [
                    "未有效檢索對話歷史",
                    "記憶整合機制不足",
                    "缺少明確的上下文指涉"
                ],
                "improvements": [
                    "🔗 主動引用前述對話（「剛才你提到...」）",
                    "🧩 將當前回應與歷史脈絡連接",
                    "📍 使用指示詞建立連貫性"
                ],
                "priority": "medium"
            },
            "depth_mismatch": {
                "triggers": ["深度不符", "專業度偏差", "技術失衡"],
                "root_causes": [
                    "未準確判斷使用者的專業背景",
                    "人格向量中的 technical_depth 設定不當",
                    "缺少動態難度調整機制"
                ],
                "improvements": [
                    "🎓 根據使用者反饋動態調整專業度",
                    "⚖️ 平衡術語與通俗解釋的比例",
                    "📊 建立專業度評分機制"
                ],
                "priority": "medium"
            }
        }
    
    async def load(self) -> bool:
        """載入模組"""
        try:
            self.log_info("正在載入反思模組...")
            self.log_info(f"📚 因果模式庫包含 {len(self.causal_library)} 種模式")
            self.log_info(f"🔬 反思深度層級: {self.reflection_depth}")
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
            "emotion_analysis": dict,
            "conversation_context": dict (optional)
        }
        
        輸出格式:
        {
            "success": bool,
            "reflection": {
                "summary": str,
                "causes": List[str],
                "improvements": List[str],
                "confidence": float,
                "meta_analysis": dict
            }
        }
        """
        try:
            user_message = data.get("user_message", "")
            assistant_message = data.get("assistant_message", "")
            emotion_analysis = data.get("emotion_analysis", {})
            conversation_context = data.get("conversation_context", {})
            
            reflection_result = await self.generate_deep_reflection(
                user_message,
                assistant_message,
                emotion_analysis,
                conversation_context
            )
            
            return {
                "success": True,
                "reflection": reflection_result,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.log_error(f"反思處理失敗: {e}")
            return {"success": False, "error": str(e)}
    
    async def generate_deep_reflection(
        self,
        user_message: str,
        assistant_message: str,
        emotion_analysis: Dict[str, Any],
        conversation_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        生成深度反思（多層級因果分析）
        
        階段：
        1. 觀察層：分析回答的表面特徵
        2. 因果層：反推導致這些特徵的根本原因（3層深度）
        3. 改進層：基於原因生成具體改進策略
        4. 元認知層：評估反思本身的質量
        """
        observation = self._observe_response(user_message, assistant_message)
        
        causes = self._causal_retrospection(
            observation,
            emotion_analysis,
            conversation_context
        )
        
        improvements = self._generate_improvements(causes, observation)
        # Actionable lessons (quality stage): always map to contract field "lessons"
        lessons = self._to_actionable_lessons(improvements, causes, observation)
        
        summary = self._synthesize_summary(causes, improvements, observation)
        
        confidence = self._calculate_reflection_confidence(causes, observation)
        # Boost confidence slightly when real multi-layer causes + lessons exist
        if len(causes) >= 2 and lessons and not any("無明顯缺陷" in c for c in causes[:1]):
            confidence = min(0.92, confidence + 0.08)
        
        meta_analysis = self._meta_cognitive_analysis(
            user_message,
            assistant_message,
            emotion_analysis,
            causes
        )
        
        return {
            "summary": summary,
            "causes": causes[:self.reflection_depth],
            "improvements": improvements[:self.reflection_depth],
            # Unified contract field (normalize_reflection already maps improvements→lessons)
            "lessons": lessons[:self.reflection_depth],
            "confidence": confidence,
            "observation": observation,
            "meta_analysis": meta_analysis,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def _observe_response(
        self,
        user_message: str,
        assistant_message: str
    ) -> Dict[str, Any]:
        """
        觀察層：分析回答的表面特徵
        """
        return {
            "length": len(assistant_message),
            "length_category": self._categorize_length(len(assistant_message)),
            "has_examples": self._detect_examples(assistant_message),
            "has_structure": self._detect_structure(assistant_message),
            "question_addressed": self._check_question_addressed(user_message, assistant_message),
            "word_overlap_ratio": self._calculate_word_overlap(user_message, assistant_message),
            "sentence_count": assistant_message.count("。") + assistant_message.count("！") + assistant_message.count("？"),
            "has_emotional_words": self._detect_emotional_language(assistant_message)
        }
    
    def _causal_retrospection(
        self,
        observation: Dict[str, Any],
        emotion_analysis: Dict[str, Any],
        conversation_context: Optional[Dict[str, Any]]
    ) -> List[str]:
        """
        因果反推層：從「果」（觀察到的現象）反推「因」（根本原因）
        
        使用三層因果分析：
        - Level 1: 直接原因（表面症狀）
        - Level 2: 間接原因（中層機制）
        - Level 3: 系統性原因（深層結構）
        """
        causes = []
        
        length_cat = observation["length_category"]
        if length_cat == "too_short":
            causes.append("【L1-直接】回應長度不足（{} 字）：可能對問題理解不夠深入".format(observation["length"]))
            causes.append("【L2-間接】資訊檢索不充分：未調用足夠的記憶或知識")
            causes.append("【L3-系統】保守策略主導：為避免錯誤而選擇最小化回應")
        elif length_cat == "too_long":
            causes.append("【L1-直接】回應過長可能造成資訊過載")
            causes.append("【L2-間接】缺少精煉與重點提取能力")
        
        if not observation["has_structure"]:
            causes.append("【L1-直接】回應缺乏清晰結構：未採用總-分-總框架")
            causes.append("【L2-間接】思考框架未激活：prompt engineering 可能不足")
        
        if not observation["has_examples"]:
            causes.append("【L1-直接】缺少具體範例：抽象程度過高")
            causes.append("【L2-間接】記憶檢索未優先具體案例")
        
        if observation["word_overlap_ratio"] < 0.2:
            causes.append("【L1-直接】回應與問題語義距離較遠")
            causes.append("【L3-系統】問題理解模組需要強化")
        
        emotion = emotion_analysis.get("dominant_emotion", "neutral")
        intensity = emotion_analysis.get("intensity", 0.5)
        
        if emotion in ["sadness", "fear", "anger"] and intensity > self.quality_thresholds["high_emotion_threshold"]:
            if not observation["has_emotional_words"]:
                causes.append(f"【L1-直接】使用者情緒為 {emotion}（{intensity:.2f}），但回應缺乏同理心表達")
                causes.append("【L2-間接】情感分析結果未充分整合到生成策略中")
                causes.append("【L3-系統】人格向量中 empathy 參數可能需要提升")
        
        if not causes:
            causes.append("【L1】回應基本達標，無明顯缺陷")
            causes.append("【L2】持續優化細節表達與個性化程度")
            causes.append("【L3】探索更深層次的語義連接與創新表達")
        
        return causes
    
    def _generate_improvements(
        self,
        causes: List[str],
        observation: Dict[str, Any]
    ) -> List[str]:
        """
        改進層：基於因果分析生成具體可執行的改進策略
        """
        improvements = []
        
        for cause in causes:
            if "長度不足" in cause or "過短" in cause:
                improvements.append("💡 內容增強：添加 2-3 個具體範例或場景模擬")
                improvements.append("📚 記憶整合：優先檢索與問題相關的歷史對話")
            
            if "缺乏結構" in cause or "結構" in cause:
                improvements.append("📐 結構化：採用「觀點-證據-結論」三段論")
                improvements.append("🎯 清晰分層：使用「首先」「其次」「最後」等連接詞")
            
            if "範例" in cause or "具體" in cause:
                improvements.append("🌟 案例化：將抽象概念轉換為生活化例子")
                improvements.append("🔍 情境重現：創建「假設...那麼...」的場景")
            
            if "同理心" in cause or "情緒" in cause:
                improvements.append("❤️ 情感共鳴三步驟：確認感受 → 給予支持 → 提供方案")
                improvements.append("🤝 柔化表達：增加「我理解」「我懂得」等同理語句")
            
            if "語義距離" in cause or "理解" in cause:
                improvements.append("🔗 主題錨定：在回應中明確回應問題核心")
                improvements.append("📍 關鍵詞呼應：重複使用問題中的核心詞彙")
            
            if "記憶檢索" in cause:
                improvements.append("🧠 增強回憶：提高向量相似度搜尋的權重")
                improvements.append("📊 上下文擴展：將檢索範圍從 5 條擴大到 10 條")
        
        if not improvements:
            improvements.append("✨ 保持現有優勢，微調表達細節")
            improvements.append("🚀 探索創新角度，提升回應驚喜感")
        
        return improvements
    
    def _to_actionable_lessons(
        self,
        improvements: List[str],
        causes: List[str],
        observation: Dict[str, Any],
    ) -> List[str]:
        """
        Quality stage: convert improvements into concrete next-action lessons
        (insight, not hollow summary).
        """
        lessons: List[str] = []
        for imp in improvements or []:
            text = str(imp).strip()
            # strip decorative emoji prefixes for cleaner storage
            for pfx in ("💡 ", "📚 ", "📐 ", "🎯 ", "🌟 ", "🔍 ", "❤️ ", "🤝 ", "🔗 ", "📍 ", "🧠 ", "📊 ", "✨ ", "🚀 "):
                if text.startswith(pfx):
                    text = text[len(pfx):]
                    break
            if not text:
                continue
            if not text.startswith("下次") and "應" not in text[:4]:
                text = f"下次回應時：{text}"
            if text not in lessons:
                lessons.append(text)
        if not lessons and causes:
            lessons.append("下次回應時：先對齊使用者核心意圖，再補一個具體例子或可執行建議")
        if observation.get("length_category") == "too_short" and not any(
            "長度" in L or "範例" in L for L in lessons
        ):
            lessons.append("下次回應時：在簡短確認後至少補充一句具體例子或下一步")
        return lessons[: max(3, self.reflection_depth)]

    def _synthesize_summary(
        self,
        causes: List[str],
        improvements: List[str],
        observation: Dict[str, Any]
    ) -> str:
        """
        摘要層：綜合反思結果 → 必須含 insight（因果 + 後續方向），非空洞客套。
        """
        if not causes:
            return "核心發現：回應大致達標；後續應維持對齊意圖並補具體性。"
        
        primary_cause = causes[0] if causes else "無明顯問題"
        core_issue = primary_cause.split("】")[1] if "】" in primary_cause else primary_cause
        
        next_step = ""
        if improvements:
            raw = str(improvements[0])
            for pfx in ("💡 ", "📚 ", "📐 ", "🎯 ", "🌟 ", "🔍 ", "❤️ ", "🤝 ", "🔗 ", "📍 ", "🧠 ", "📊 ", "✨ ", "🚀 "):
                if raw.startswith(pfx):
                    raw = raw[len(pfx):]
                    break
            next_step = raw
        
        summary = f"核心發現：{core_issue}。"
        if next_step:
            summary += f" 後續方向：{next_step}。"
        else:
            summary += f" 已完成 {len(causes)} 層因果分析，需轉成可執行的下次調整。"
        
        if observation.get("length_category") in ["too_short", "too_long"]:
            summary += f" 長度訊號：當前 {observation.get('length', 0)} 字需校正。"
        
        return summary
    
    def _calculate_reflection_confidence(
        self,
        causes: List[str],
        observation: Dict[str, Any]
    ) -> float:
        """
        計算反思置信度（這次反思有多可靠）
        """
        base_confidence = 0.6
        
        if len(causes) >= 3:
            base_confidence += 0.1
        
        specific_keywords = ["因為", "導致", "缺少", "不足", "需要"]
        specificity = sum(1 for cause in causes for kw in specific_keywords if kw in cause)
        specificity_score = min(specificity / (len(causes) * 2), 0.2)
        base_confidence += specificity_score
        
        if observation["length"] > 0:
            base_confidence += 0.1
        
        return min(base_confidence, 0.95)
    
    def _meta_cognitive_analysis(
        self,
        user_message: str,
        assistant_message: str,
        emotion_analysis: Dict[str, Any],
        causes: List[str]
    ) -> Dict[str, Any]:
        """
        元認知層：反思這次反思本身的質量
        """
        return {
            "query_complexity": self._assess_query_complexity(user_message),
            "response_quality_score": self._score_response_quality(assistant_message, causes),
            "emotion_alignment": self._check_emotion_alignment(emotion_analysis, assistant_message),
            "causal_depth": len([c for c in causes if "L3" in c or "L2" in c]),
            "actionable_improvements": len([i for i in self._generate_improvements(causes, {}) if "💡" in i or "🎯" in i])
        }
    
    def _categorize_length(self, length: int) -> str:
        """分類回應長度"""
        if length < self.quality_thresholds["min_response_length"]:
            return "too_short"
        elif length > self.quality_thresholds["max_response_length"]:
            return "too_long"
        else:
            return "appropriate"
    
    def _detect_examples(self, text: str) -> bool:
        """檢測是否包含範例"""
        example_markers = ["例如", "比如", "舉例", "譬如", "像是", "假設", "情境"]
        return any(marker in text for marker in example_markers)
    
    def _detect_structure(self, text: str) -> bool:
        """檢測是否有結構化表達"""
        structure_markers = ["首先", "其次", "再者", "最後", "總之", "綜上", "第一", "第二"]
        return any(marker in text for marker in structure_markers) or text.count("。") >= 3
    
    def _check_question_addressed(self, question: str, answer: str) -> bool:
        """檢查是否回應了問題"""
        if "？" in question or "?" in question:
            return len(answer) > 20
        return True
    
    def _calculate_word_overlap(self, text1: str, text2: str) -> float:
        """計算詞彙重疊率"""
        words1 = set(text1)
        words2 = set(text2)
        if not words1:
            return 0.0
        return len(words1 & words2) / len(words1)
    
    def _detect_emotional_language(self, text: str) -> bool:
        """檢測情感性語言"""
        emotional_words = ["理解", "感受", "支持", "同情", "關心", "擔心", "希望", "相信"]
        return any(word in text for word in emotional_words)
    
    def _assess_query_complexity(self, query: str) -> str:
        """評估問題複雜度"""
        length = len(query)
        questions = query.count("？") + query.count("?")
        
        if length > 100 or questions > 2:
            return "high"
        elif length > 50 or questions > 1:
            return "medium"
        return "low"
    
    def _score_response_quality(self, response: str, causes: List[str]) -> float:
        """評分回應質量"""
        score = 0.5
        
        if len(response) >= self.quality_thresholds["ideal_response_length_range"][0]:
            score += 0.2
        
        if len([c for c in causes if "L1" in c and "達標" not in c]) == 0:
            score += 0.3
        
        return min(score, 1.0)
    
    def _check_emotion_alignment(self, emotion_analysis: Dict, response: str) -> float:
        """檢查情感對齊度"""
        emotion = emotion_analysis.get("dominant_emotion", "neutral")
        
        if emotion in ["sadness", "fear", "anger"]:
            if self._detect_emotional_language(response):
                return 0.8
            return 0.3
        
        return 0.6
    
    async def health_check(self) -> Dict[str, Any]:
        """健康檢查"""
        return {
            "status": "healthy",
            "enabled": self.enabled,
            "reflection_depth": self.reflection_depth,
            "causal_patterns_count": len(self.causal_library),
            "quality_thresholds": self.quality_thresholds
        }
