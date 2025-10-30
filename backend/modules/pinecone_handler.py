"""
Pinecone 向量資料庫處理器 - Pinecone Vector Database Handler
負責將反思的人格向量儲存到 Pinecone 以便後續檢索
使用 Pinecone 內建的 llama-text-embed-v2 模型生成向量
"""
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
import json


class PineconeHandler:
    """Pinecone 向量資料庫接口類"""

    def __init__(self):
        """初始化 Pinecone 連接"""
        self.api_key = os.getenv("PINECONE_API_KEY")
        self.environment = os.getenv("PINECONE_ENVIRONMENT")
        self.index_name = os.getenv("PINECONE_INDEX_NAME")
        
        self.pc = None
        self.index = None
        self.embed_model = None
        self.initialized = False
        
        if self.api_key and self.index_name:
            self._initialize_pinecone()
        else:
            print("⚠️ Pinecone 環境變數未設定，向量儲存功能將被禁用")

    def _initialize_pinecone(self):
        """初始化 Pinecone 客戶端和索引（不預先載入 embedding 模型）"""
        try:
            from pinecone import Pinecone, ServerlessSpec
            
            self.pc = Pinecone(api_key=self.api_key)
            print(f"✅ Pinecone 客戶端已初始化")
            
            existing_indexes = [index.name for index in self.pc.list_indexes()]
            
            if self.index_name not in existing_indexes:
                print(f"🔧 建立新的 Pinecone 索引: {self.index_name}")
                self.pc.create_index(
                    name=self.index_name,
                    dimension=4096,
                    metric='cosine',
                    spec=ServerlessSpec(
                        cloud='aws',
                        region=self.environment or 'us-east-1'
                    )
                )
                print(f"✅ Pinecone 索引已建立 (dimension=4096, metric=cosine)")
            else:
                print(f"✅ Pinecone 索引已存在: {self.index_name}")
            
            self.index = self.pc.Index(self.index_name)
            self.initialized = True
            print(f"✅ Pinecone 向量資料庫已就緒 (使用 llama-text-embed-v2 模型)")
            
        except Exception as e:
            print(f"❌ Pinecone 初始化失敗: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            self.initialized = False

    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        使用 Pinecone 的 llama-text-embed-v2 生成文本向量
        
        參數:
            text: 要生成向量的文本
        
        返回:
            向量列表或 None
        """
        if not self.initialized:
            print("⚠️ Pinecone 未初始化，無法生成向量")
            return None
        
        try:
            response = self.pc.inference.embed(
                model="llama-text-embed-v2",
                inputs=[text],
                parameters={"input_type": "passage"}
            )
            
            if response and len(response.data) > 0:
                embedding = response.data[0].values
                print(f"✅ 生成向量成功 (維度: {len(embedding)})")
                return embedding
            else:
                print("⚠️ Pinecone 返回空向量")
                return None
                
        except Exception as e:
            print(f"❌ Pinecone 生成向量失敗: {type(e).__name__}: {e}")
            return None

    def store_reflection_vector(
        self,
        reflection_id: str,
        embedding: List[float],
        metadata: Dict[str, Any]
    ) -> bool:
        """
        儲存反思向量到 Pinecone
        
        參數:
            reflection_id: 反思記錄的唯一 ID
            embedding: 4096 維的向量（從 Pinecone llama-text-embed-v2 生成）
            metadata: 元數據（包含摘要、標籤、時間等）
        
        返回:
            是否成功
        """
        if not self.initialized:
            print("⚠️ Pinecone 未初始化，跳過向量儲存")
            return False
        
        try:
            safe_metadata = self._sanitize_metadata(metadata)
            
            self.index.upsert(
                vectors=[{
                    "id": reflection_id,
                    "values": embedding,
                    "metadata": safe_metadata
                }]
            )
            
            print(f"✅ 反思向量已儲存到 Pinecone: {reflection_id}")
            return True
            
        except Exception as e:
            print(f"❌ Pinecone 向量儲存失敗: {type(e).__name__}: {e}")
            return False
    
    def store_reflection_with_text(
        self,
        reflection_id: str,
        reflection_text: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """
        從文本自動生成向量並儲存到 Pinecone
        
        參數:
            reflection_id: 反思記錄的唯一 ID
            reflection_text: 反思摘要文本（用於生成向量）
            metadata: 元數據
        
        返回:
            是否成功
        """
        embedding = self.generate_embedding(reflection_text)
        
        if embedding is None:
            print("⚠️ 向量生成失敗，跳過儲存")
            return False
        
        return self.store_reflection_vector(reflection_id, embedding, metadata)

    def query_similar_reflections(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        查詢相似的反思向量
        
        參數:
            query_embedding: 查詢向量
            top_k: 返回前 K 個最相似結果
            filter_metadata: 元數據過濾條件（可選）
        
        返回:
            相似反思列表
        """
        if not self.initialized:
            print("⚠️ Pinecone 未初始化，無法查詢")
            return []
        
        try:
            query_params = {
                "vector": query_embedding,
                "top_k": top_k,
                "include_metadata": True
            }
            
            if filter_metadata:
                query_params["filter"] = filter_metadata
            
            results = self.index.query(**query_params)
            
            similar_reflections = []
            for match in results.get("matches", []):
                similar_reflections.append({
                    "id": match.get("id"),
                    "score": match.get("score"),
                    "metadata": match.get("metadata", {})
                })
            
            print(f"🔍 找到 {len(similar_reflections)} 個相似反思")
            return similar_reflections
            
        except Exception as e:
            print(f"❌ Pinecone 查詢失敗: {type(e).__name__}: {e}")
            return []

    def delete_reflection(self, reflection_id: str) -> bool:
        """
        刪除指定的反思向量
        
        參數:
            reflection_id: 反思記錄 ID
        
        返回:
            是否成功
        """
        if not self.initialized:
            return False
        
        try:
            self.index.delete(ids=[reflection_id])
            print(f"✅ 已從 Pinecone 刪除反思: {reflection_id}")
            return True
        except Exception as e:
            print(f"❌ Pinecone 刪除失敗: {e}")
            return False

    def _sanitize_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        清理元數據（Pinecone 限制：值必須是字串、數字、布林或列表）
        """
        sanitized = {}
        
        for key, value in metadata.items():
            if isinstance(value, (str, int, float, bool)):
                sanitized[key] = value
            elif isinstance(value, (dict, list)):
                sanitized[key] = json.dumps(value, ensure_ascii=False)
            elif value is None:
                sanitized[key] = ""
            else:
                sanitized[key] = str(value)
        
        return sanitized

    def get_stats(self) -> Dict[str, Any]:
        """
        獲取 Pinecone 統計資訊
        
        返回:
            統計資訊
        """
        if not self.initialized:
            return {
                "status": "disabled",
                "reason": "Pinecone 環境變數未設定"
            }
        
        try:
            stats = self.index.describe_index_stats()
            return {
                "status": "active",
                "index_name": self.index_name,
                "total_vectors": stats.get("total_vector_count", 0),
                "dimension": stats.get("dimension", 1536)
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
