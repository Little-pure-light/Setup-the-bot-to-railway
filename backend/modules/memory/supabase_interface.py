"""
Supabase 長期記憶接口 - Supabase Long-term Memory Interface
負責永久儲存 Token 化資料與反思紀錄
"""
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
import os

class SupabaseInterface:
    """Supabase 長期記憶接口類"""
    
    def __init__(self, supabase_client=None, config: Optional[Dict[str, Any]] = None):
        """
        初始化 Supabase 接口
        
        參數:
            supabase_client: Supabase 客戶端
            config: 模組配置（包含表名與欄位映射）
        """
        self.supabase = supabase_client
        self.config = config or {}
        
        self.tables = self.config.get("tables", {
            "conversations": "xiaochenguang_memories",
            "memories": "xiaochenguang_memories",
            "reflections": "xiaochenguang_reflections"
        })
        
        self.columns_map = self.config.get("columns_map", {})
        
        if self.supabase is None:
            self._init_supabase_client()
    
    def _init_supabase_client(self):
        """初始化 Supabase 客戶端"""
        try:
            from backend.supabase_handler import supabase
            self.supabase = supabase
            print("✅ Supabase Interface 已初始化")
        except ImportError:
            print("⚠️ 無法載入 Supabase 客戶端")
            self.supabase = None
    
    def commit_to_longterm(
        self, 
        records: List[Dict[str, Any]]
    ) -> int:
        """
        批次寫入長期記憶到 Supabase
        
        參數:
            records: 記憶記錄列表
        
        返回:
            成功寫入的筆數
        """
        if not self.supabase or not records:
            return 0
        
        success_count = 0
        table_name = self.tables.get("conversations", "xiaochenguang_memories")
        
        for record in records:
            try:
                mapped_record = self._map_record(record)
                
                result = self.supabase.table(table_name).upsert(
                    mapped_record,
                    on_conflict="id" if "id" in mapped_record else None
                ).execute()
                
                if result:
                    success_count += 1
                
            except Exception as e:
                print(f"❌ Supabase 寫入失敗: {e}")
                continue
        
        return success_count
    
    def store_single_memory(
        self, 
        record: Dict[str, Any]
    ) -> bool:
        """
        儲存單筆記憶
        
        參數:
            record: 記憶記錄
        
        返回:
            是否成功
        """
        return self.commit_to_longterm([record]) > 0
    
    def store_reflection(
        self, 
        reflection_data: Dict[str, Any]
    ) -> Optional[str]:
        """
        儲存反思記錄
        
        參數:
            reflection_data: 反思資料
        
        返回:
            反思 ID 或 None
        """
        if not self.supabase:
            return None
        
        try:
            table_name = self.tables.get("reflections", "xiaochenguang_reflections")
            
            reflection_record = {
                "conversation_id": reflection_data.get("conversation_id"),
                "user_id": reflection_data.get("user_id"),
                "reflection_content": json.dumps(reflection_data.get("reflection", {}), ensure_ascii=False),
                "token_data": reflection_data.get("token_data", {}),
                "cid": reflection_data.get("cid"),
                "feedback_loop_id": reflection_data.get("feedback_loop_id"),
                "created_at": reflection_data.get("created_at", datetime.utcnow().isoformat())
            }
            
            result = self.supabase.table(table_name).insert(
                reflection_record
            ).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0].get("id")
            
            return None
            
        except Exception as e:
            print(f"❌ 反思記錄儲存失敗: {e}")
            return None
    
    def get_conversation_memories(
        self, 
        conversation_id: str, 
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        獲取對話記憶
        
        參數:
            conversation_id: 對話 ID
            limit: 最大返回數量
        
        返回:
            記憶列表
        """
        if not self.supabase:
            return []
        
        try:
            table_name = self.tables.get("conversations", "xiaochenguang_memories")
            
            result = self.supabase.table(table_name)\
                .select("*")\
                .eq("conversation_id", conversation_id)\
                .order("created_at", desc=True)\
                .limit(limit)\
                .execute()
            
            return result.data if result.data else []
            
        except Exception as e:
            print(f"❌ 獲取對話記憶失敗: {e}")
            return []
    
    def get_user_reflections(
        self, 
        user_id: str, 
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        獲取使用者的反思記錄
        
        參數:
            user_id: 使用者 ID
            limit: 最大返回數量
        
        返回:
            反思列表
        """
        if not self.supabase:
            return []
        
        try:
            table_name = self.tables.get("reflections", "xiaochenguang_reflections")
            
            result = self.supabase.table(table_name)\
                .select("*")\
                .eq("user_id", user_id)\
                .order("created_at", desc=True)\
                .limit(limit)\
                .execute()
            
            return result.data if result.data else []
            
        except Exception as e:
            print(f"❌ 獲取反思記錄失敗: {e}")
            return []
    
    def update_cid(
        self, 
        record_id: str, 
        cid: str, 
        table_type: str = "conversations"
    ) -> bool:
        """
        更新記錄的 IPFS CID
        
        參數:
            record_id: 記錄 ID
            cid: IPFS CID
            table_type: 表類型
        
        返回:
            是否成功
        """
        if not self.supabase:
            return False
        
        try:
            table_name = self.tables.get(table_type, "xiaochenguang_memories")
            
            result = self.supabase.table(table_name)\
                .update({"cid": cid})\
                .eq("id", record_id)\
                .execute()
            
            return bool(result.data)
            
        except Exception as e:
            print(f"❌ 更新 CID 失敗: {e}")
            return False
    
    def _map_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        根據欄位映射轉換記錄
        
        參數:
            record: 原始記錄
        
        返回:
            映射後的記錄
        """
        if not self.columns_map:
            return record
        
        mapped = {}
        for standard_key, value in record.items():
            actual_key = self.columns_map.get(standard_key, standard_key)
            mapped[actual_key] = value
        
        return mapped
    
    def get_stats(self) -> Dict[str, Any]:
        """
        獲取 Supabase 統計資訊
        
        返回:
            統計資訊
        """
        if not self.supabase:
            return {"status": "unavailable"}
        
        try:
            table_name = self.tables.get("conversations", "xiaochenguang_memories")
            
            result = self.supabase.table(table_name)\
                .select("id", count="exact")\
                .execute()
            
            return {
                "status": "active",
                "total_memories": result.count if hasattr(result, 'count') else 0,
                "table": table_name
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
