# pinecone_handler.py
# 目的：維持原檔名與介面，但全面更新至最新 API 與 1536 維工作流
# 需要：pip install --upgrade openai pinecone python-dotenv

import os
import json
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec

# ---- 常數（對齊你的新索引）----
EMBED_MODEL = "text-embedding-3-small"  # 1536-d
EXPECTED_DIM = 1536


class PineconeHandler:
    """
    保留類別名 PineconeHandler，不更名。
    - 使用 OpenAI Embeddings (text-embedding-3-small, 1536 維)
    - 使用 Pinecone v3/v7 API：from pinecone import Pinecone
    - 自動建立/檢查 index（serverless, aws/us-east-1）
    - 提供向後相容 method 別名（見底部 alias）
    """

    def __init__(self):
        load_dotenv()

        self.pinecone_api_key = os.getenv("PINECONE_API_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.index_name = os.getenv("PINECONE_INDEX_NAME", "xiaochenguang-reflections-v2")
        self.region = os.getenv("PINECONE_ENVIRONMENT", "us-east-1")  # serverless region
        if not self.pinecone_api_key:
            raise ValueError("缺少 PINECONE_API_KEY")
        if not self.openai_api_key:
            raise ValueError("缺少 OPENAI_API_KEY")

        # 初始化新版客戶端
        self.pc = Pinecone(api_key=self.pinecone_api_key)
        self.openai = OpenAI(api_key=self.openai_api_key)

        # 確保/連線索引
        self._ensure_index()
        self.index = self.pc.Index(self.index_name)

    # ---------------- Core ----------------

    def _ensure_index(self) -> None:
        """不存在就建立；存在則檢查維度"""
        existing = [i.name for i in self.pc.list_indexes()]
        if self.index_name not in existing:
            self.pc.create_index(
                name=self.index_name,
                dimension=EXPECTED_DIM,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region=self.region),
            )
        # 維度確認
        desc = self.pc.describe_index(self.index_name)
        dim = getattr(desc, "dimension", EXPECTED_DIM)
        if dim != EXPECTED_DIM:
            raise RuntimeError(
                f"Pinecone index 維度為 {dim}，預期 {EXPECTED_DIM}。請確認你用的是 1536 維索引。"
            )

    def generate_embedding(self, text: str) -> List[float]:
        """產生 1536 維 embedding（新版 OpenAI 語法）"""
        resp = self.openai.embeddings.create(model=EMBED_MODEL, input=text)
        return resp.data[0].embedding

    def insert_reflection(self, reflection_id: str, content: str, metadata: Dict[str, Any]) -> None:
        """
        上傳一筆向量（以 reflection_id 為向量 id）
        metadata 僅允許基本型別；複雜型別會自動 json 化
        """
        embedding = self.generate_embedding(content)
        clean_meta = self._sanitize_metadata(metadata)

        self.index.upsert([{
            "id": reflection_id,
            "values": embedding,
            "metadata": clean_meta
        }])

    def query_similar(self, text: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """以文字查詢相似向量（回傳 matches 清單）"""
        vec = self.generate_embedding(text)
        res = self.index.query(vector=vec, top_k=top_k, include_metadata=True)
        # 新 SDK 回傳 dict-like；統一成 list[dict]
        matches = res.get("matches", []) if isinstance(res, dict) else getattr(res, "matches", [])
        return matches or []

    def delete_reflection(self, reflection_id: str) -> None:
        """刪除特定 id 的向量"""
        self.index.delete(ids=[reflection_id])

    # ---------------- Utils ----------------

    @staticmethod
    def _sanitize_metadata(meta: Dict[str, Any]) -> Dict[str, Any]:
        """確保 metadata 可被 Pinecone 接受（基本型別；其他轉 json 字串）"""
        clean = {}
        for k, v in meta.items():
            if isinstance(v, (str, int, float, bool)) or v is None:
                clean[k] = v
            else:
                try:
                    clean[k] = json.dumps(v, ensure_ascii=False)
                except Exception:
                    clean[k] = str(v)
        return clean

    # ---------------- Backward-compatible aliases ----------------
    # 下面幾個別名是為了防止你原本的呼叫壞掉。
    # 若舊程式使用 upsert/query/delete 這些短名，依然可用。

    def upsert(self, reflection_id: str, content: str, metadata: Dict[str, Any]) -> None:
        """別名 → insert_reflection"""
        self.insert_reflection(reflection_id, content, metadata)

    def query(self, text: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """別名 → query_similar"""
        return self.query_similar(text, top_k=top_k)

    def delete(self, reflection_id: str) -> None:
        """別名 → delete_reflection"""
        self.delete_reflection(reflection_id)
