"""
知識庫模組 - Knowledge Hub
全域共享資料層，負責知識的結構化與索引
"""
from typing import Dict, Any, Optional
from backend.base_module import BaseModule


class KnowledgeHub(BaseModule):
    """知識庫模組類別"""
    
    def __init__(self, module_name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(module_name, config)
        self.knowledge_index = {}
    
    async def load(self) -> bool:
        """載入模組"""
        try:
            self.log_info("正在載入知識庫模組...")
            self._initialized = True
            self.log_info("✅ 知識庫模組載入完成")
            return True
        except Exception as e:
            self.log_error(f"載入失敗: {e}")
            return False
    
    async def unload(self) -> bool:
        """卸載模組"""
        try:
            self.log_info("正在卸載知識庫模組...")
            self._initialized = False
            return True
        except Exception as e:
            self.log_error(f"卸載失敗: {e}")
            return False
    
    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        處理知識相關操作
        
        支援操作:
        - index_knowledge: 索引知識
        - search_knowledge: 搜尋知識
        """
        operation = data.get("operation")
        
        if operation == "index_knowledge":
            return await self._index_knowledge(data)
        elif operation == "search_knowledge":
            return await self._search_knowledge(data)
        else:
            return {"error": f"未知操作: {operation}"}
    
    async def _index_knowledge(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """索引新知識"""
        try:
            knowledge_id = data.get("knowledge_id")
            content = data.get("content")
            metadata = data.get("metadata", {})
            
            self.knowledge_index[knowledge_id] = {
                "content": content,
                "metadata": metadata
            }
            
            return {"success": True, "knowledge_id": knowledge_id}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _search_knowledge(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """搜尋知識"""
        try:
            query = data.get("query", "")
            results = []
            
            for kid, kdata in self.knowledge_index.items():
                if query.lower() in kdata["content"].lower():
                    results.append({"id": kid, "content": kdata["content"]})
            
            return {"success": True, "results": results}
        except Exception as e:
            return {"success": False, "error": str(e)}
