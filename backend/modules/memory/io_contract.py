"""
I/O 合約層 - Input/Output Contract Layer
負責資料校驗與標準化，確保所有模組使用統一的資料結構
"""
from typing import Dict, Any, Optional
from datetime import datetime
import json

class ValidationError(Exception):
    """資料驗證錯誤"""
    pass

def validate_and_normalize(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    校驗並標準化輸入資料
    
    參數:
        payload: 原始輸入資料
    
    返回:
        標準化後的資料結構
    
    拋出:
        ValidationError: 當必要欄位缺失時
    """
    if not isinstance(payload, dict):
        raise ValidationError("payload 必須是 dict 類型")
    
    conversation_id = payload.get("conversation_id")
    user_id = payload.get("user_id")
    
    if not conversation_id:
        raise ValidationError("缺少必要欄位: conversation_id")
    
    if not user_id:
        raise ValidationError("缺少必要欄位: user_id")
    
    normalized = {
        "conversation_id": str(conversation_id),
        "user_id": str(user_id),
        "user_message": payload.get("user_message"),
        "assistant_message": payload.get("assistant_message"),
        "reflection": _normalize_reflection(payload.get("reflection")),
        "token_data": payload.get("token_data", {}),
        "cid": payload.get("cid"),
        "created_at": _normalize_timestamp(payload.get("created_at"))
    }
    
    return normalized

def _normalize_reflection(reflection: Any) -> Optional[Dict[str, Any]]:
    """
    標準化反思資料
    
    參數:
        reflection: 反思資料（可能是 dict, str, 或 None）
    
    返回:
        標準化的反思 dict 或 None
    """
    if reflection is None:
        return None
    
    if isinstance(reflection, dict):
        return {
            "summary": reflection.get("summary", ""),
            "causes": reflection.get("causes", []),
            "improvements": reflection.get("improvements", []),
            "confidence": reflection.get("confidence", 0.5)
        }
    
    if isinstance(reflection, str):
        try:
            parsed = json.loads(reflection)
            return _normalize_reflection(parsed)
        except json.JSONDecodeError:
            return {
                "summary": reflection,
                "causes": [],
                "improvements": [],
                "confidence": 0.5
            }
    
    return None

def _normalize_timestamp(timestamp: Any) -> str:
    """
    標準化時間戳
    
    參數:
        timestamp: 時間戳（可能是 str, datetime, 或 None）
    
    返回:
        ISO 8601 格式字串
    """
    if timestamp is None:
        return datetime.utcnow().isoformat()
    
    if isinstance(timestamp, datetime):
        return timestamp.isoformat()
    
    if isinstance(timestamp, str):
        return timestamp
    
    return datetime.utcnow().isoformat()

def create_memory_record(
    conversation_id: str,
    user_id: str,
    user_message: Optional[str] = None,
    assistant_message: Optional[str] = None,
    reflection: Optional[Dict[str, Any]] = None,
    token_data: Optional[Dict[str, Any]] = None,
    cid: Optional[str] = None
) -> Dict[str, Any]:
    """
    創建標準記憶記錄
    
    參數:
        conversation_id: 對話 ID
        user_id: 使用者 ID
        user_message: 使用者訊息
        assistant_message: AI 回覆
        reflection: 反思結果
        token_data: Token 資料
        cid: IPFS 索引
    
    返回:
        標準化記憶記錄
    """
    return validate_and_normalize({
        "conversation_id": conversation_id,
        "user_id": user_id,
        "user_message": user_message,
        "assistant_message": assistant_message,
        "reflection": reflection,
        "token_data": token_data or {},
        "cid": cid,
        "created_at": datetime.utcnow().isoformat()
    })

def map_columns(
    data: Dict[str, Any], 
    columns_map: Dict[str, str]
) -> Dict[str, Any]:
    """
    根據欄位映射轉換資料鍵名
    
    參數:
        data: 原始資料
        columns_map: 欄位映射表（標準名 -> 實際名）
    
    返回:
        映射後的資料
    """
    mapped = {}
    for standard_key, value in data.items():
        actual_key = columns_map.get(standard_key, standard_key)
        mapped[actual_key] = value
    return mapped
