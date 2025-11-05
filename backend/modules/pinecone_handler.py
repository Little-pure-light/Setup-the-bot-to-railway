"""
pinecone_handler_v2.py
=======================
新版 Pinecone 向量處理模組
對應 index: xiaochenguang-reflections-v2
維度: 1536
embedding 模型: text-embedding-3-large
"""

import os
import json
from typing import Dict, Any, List, Optional
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec


class PineconeHandlerV2:
    """新版 Pinecone 向量資料庫操作類"""

    def __init__(self):
        self.api_key = os.getenv("PINECONE_API_KEY")
        self.index_name = os.getenv("PINECONE_INDEX_NAME", "xiaochenguang-reflections-v2")
        self.environment = os.getenv("PINECONE_ENVIRONMENT", "us-east-1")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")

        if not self.api_key or not self.openai_api_key:
            raise ValueError("❌ 缺少必要的 API Key: PINECONE_API_KEY 或 OPENAI_API_KEY")

        # 初始化客戶端
        self.pinecone = Pinecone(api_key=self.api_key)
        self.openai = OpenAI(api_key=self.openai_api_key)

        # 初始化 index
        self._initialize_index()

    def _initialize_index(self):
        """確認 index 存在，若不存在則建立"""
        existing = [idx.name for idx in self.pinecone.list_indexes()]
        if self.index_name not in existing:
            print(f"⚙️ 未找到索引，正在建立新的索引: {self.index_name}")
            self.pinecone.create_index(
                name=self.index_name,
                dimension=1536,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region=self.environment)
            )
            print("✅ 已建立 Pinecone 索引。")

        self.index = self.pinecone.Index(self.index_name)
        print(f"✅ 已連線至 Pinecone Index: {self.index_name}")

    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """使用 OpenAI text-embedding-3-large 生成 1536 維向量"""
        try:
            response = self.openai.embeddings.create(
                model="text-embedding-3-large",
                input=text
            )
            embedding = response.data[0].embedding
            return embedding
        except Exception as e:
            print(f"❌ 生成 embedding 失敗: {e}")
            return None

    def insert_reflection(self, reflection_id: str, content: str, metadata: Dict[str, Any]):
        """將反思資料寫入 Pinecone"""
        embedding = self.generate_embedding(content)
        if not embedding:
            print(f"⚠️ 無法為 {reflection_id} 生成 embedding，已跳過。")
            return

        # 清理 metadata，確保符合 Pinecone 格式
        clean_meta = self._sanitize_metadata(metadata)

        try:
            self.index.upsert([
                {
                    "id": reflection_id,
                    "values": embedding,
                    "metadata": clean_meta
                }
            ])
            print(f"✅ 已寫入 Pinecone: {reflection_id}")
        except Exception as e:
            print(f"❌ 上傳至 Pinecone 失敗: {e}")

    def query_similar(self, text: str, top_k: int = 5):
        """查詢與輸入文本最相似的反思內容"""
        embedding = self.generate_embedding(text)
        if not embedding:
            return []

        try:
            result = self.index.query(
                vector=embedding,
                top_k=top_k,
                include_metadata=True
            )
            return result["matches"]
        except Exception as e:
            print(f"❌ 查詢失敗: {e}")
            return []

    def delete_reflection(self, reflection_id: str):
        """刪除特定反思資料"""
        try:
            self.index.delete(ids=[reflection_id])
            print(f"🗑️ 已刪除向量：{reflection_id}")
        except Exception as e:
            print(f"❌ 刪除失敗: {e}")

    @staticmethod
    def _sanitize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
        """確保 metadata 全部轉成字串或基本型別"""
        clean = {}
        for k, v in metadata.items():
            if isinstance(v, (str, int, float, bool)):
                clean[k] = v
            else:
                clean[k] = json.dumps(v, ensure_ascii=False)
        return clean
