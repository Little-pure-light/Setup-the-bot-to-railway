"""
Token 化引擎 - Tokenizer Engine
負責將文字轉換為數字化 token 序列
支援 tiktoken 與降級方案
"""
import os
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

class TokenizerEngine:
    """Token 化引擎核心類"""
    
    def __init__(self, tokenizer_name: str = None):
        """
        初始化 Tokenizer
        
        參數:
            tokenizer_name: tiktoken 編碼器名稱（如 cl100k_base）
        """
        self.tokenizer_name = tokenizer_name or os.getenv("TOKENIZER_NAME", "cl100k_base")
        self.encoding = None
        self.fallback_mode = False
        
        self._initialize_tokenizer()
    
    def _initialize_tokenizer(self):
        """初始化 tokenizer（優先 tiktoken，失敗則降級）"""
        try:
            import tiktoken
            self.encoding = tiktoken.get_encoding(self.tokenizer_name)
            print(f"✅ Tokenizer 已初始化（tiktoken: {self.tokenizer_name}）")
        except ImportError:
            print("⚠️ tiktoken 未安裝，使用降級方案（UTF-8 bytes）")
            self.fallback_mode = True
        except Exception as e:
            print(f"⚠️ tiktoken 初始化失敗: {e}，使用降級方案")
            self.fallback_mode = True
    
    def tokenize_text(self, text: str) -> List[int]:
        """
        將文字轉換為 token 序列
        
        參數:
            text: 輸入文字
        
        返回:
            token 整數序列
        """
        if not text:
            return []
        
        if self.fallback_mode:
            return self._fallback_tokenize(text)
        
        try:
            return self.encoding.encode(text)
        except Exception as e:
            print(f"⚠️ tiktoken 編碼失敗: {e}，使用降級方案")
            return self._fallback_tokenize(text)
    
    def _fallback_tokenize(self, text: str) -> List[int]:
        """
        降級方案：使用 UTF-8 bytes 作為 token
        
        參數:
            text: 輸入文字
        
        返回:
            UTF-8 bytes 序列
        """
        return list(text.encode('utf-8'))
    
    def decode_tokens(self, tokens: List[int]) -> str:
        """
        將 token 序列解碼為文字（僅用於調試）
        
        參數:
            tokens: token 整數序列
        
        返回:
            解碼後的文字
        """
        if not tokens:
            return ""
        
        if self.fallback_mode:
            try:
                return bytes(tokens).decode('utf-8', errors='ignore')
            except Exception:
                return ""
        
        try:
            return self.encoding.decode(tokens)
        except Exception as e:
            print(f"⚠️ 解碼失敗: {e}")
            return ""
    
    def pack_token_record(
        self, 
        user: Optional[str] = None, 
        assistant: Optional[str] = None, 
        reflection_json: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        將對話內容打包為完整的 token 記錄
        
        參數:
            user: 使用者訊息
            assistant: AI 回覆
            reflection_json: 反思結果（dict）
        
        返回:
            完整的 token 資料結構
        """
        token_data = {
            "user": self.tokenize_text(user) if user else [],
            "assistant": self.tokenize_text(assistant) if assistant else [],
            "reflection": [],
            "method": "tiktoken" if not self.fallback_mode else "utf8_bytes",
            "encoding": self.tokenizer_name if not self.fallback_mode else "utf-8",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if reflection_json:
            reflection_text = json.dumps(reflection_json, ensure_ascii=False)
            token_data["reflection"] = self.tokenize_text(reflection_text)
        
        token_data["total_count"] = (
            len(token_data["user"]) + 
            len(token_data["assistant"]) + 
            len(token_data["reflection"])
        )
        
        return token_data
    
    def get_token_count(self, text: str) -> int:
        """
        獲取文字的 token 數量
        
        參數:
            text: 輸入文字
        
        返回:
            token 數量
        """
        return len(self.tokenize_text(text))
    
    def create_context_record(
        self, 
        text: str, 
        context_id: str, 
        record_type: str = "chat_message"
    ) -> Dict[str, Any]:
        """
        創建完整的上下文記錄
        
        參數:
            text: 文字內容
            context_id: 上下文 ID
            record_type: 記錄類型（chat_message, reflection, knowledge）
        
        返回:
            完整記錄結構
        """
        return {
            "text": text,
            "tokens": self.tokenize_text(text),
            "encoding": self.tokenizer_name if not self.fallback_mode else "utf-8",
            "context_id": context_id,
            "type": record_type,
            "token_count": self.get_token_count(text),
            "timestamp": datetime.utcnow().isoformat()
        }
