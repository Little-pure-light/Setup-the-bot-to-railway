"""
RetrievalEngine — type-aware + embedding retrieval (Phase 2 + Fix ranking).

Flow:
  Intent → Memory Type → Embedding Search → Graph Expansion → Rank → Response

Ranking considers:
  vector similarity, memory_type match, importance, recency, graph relation confidence
"""
from __future__ import annotations

import logging
import math
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from backend.modules.memory_types import MEMORY_TYPES, V1_CONVERSATION_TYPE

logger = logging.getLogger("memory.retrieval")

_IDENTITY_Q = re.compile(r"(你是誰|你叫|名字|身份|who are you|your name)", re.I)
_SEMANTIC_Q = re.compile(r"(什麼是|如何|怎麼|為什麼|定義|what is|how to|explain)", re.I)
_EPISODIC_Q = re.compile(r"(記得|上次|之前|那天|還記得|last time|remember)", re.I)
_EMOTION_Q = re.compile(r"(心情|感覺|難過|開心|feel|emotion|mood)", re.I)
_PERSONA_Q = re.compile(r"(人格|性格|你變|成長|personality|reflect)", re.I)


def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _parse_ts(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        s = str(value).replace("Z", "+00:00")
        return datetime.fromisoformat(s).timestamp()
    except Exception:
        return 0.0


class RetrievalEngine:
    def __init__(self, memory_system, graph_manager=None):
        self.ms = memory_system
        self.graph = graph_manager

    def infer_types(self, query: str) -> List[str]:
        q = query or ""
        types: List[str] = []
        if _IDENTITY_Q.search(q):
            types.append("identity")
        if _SEMANTIC_Q.search(q):
            types.append("semantic")
        if _EPISODIC_Q.search(q):
            types.append("episodic")
        if _EMOTION_Q.search(q):
            types.append("emotion")
        if _PERSONA_Q.search(q):
            types.extend(["reflection", "transformation"])
        if not types:
            types = ["episodic"]
        seen = set()
        out = []
        for t in types:
            if t not in seen:
                seen.add(t)
                out.append(t)
        return out

    def _embed(self, text: str) -> Optional[List[float]]:
        if self.ms is None or not getattr(self.ms, "openai_client", None):
            return None
        try:
            model = __import__("os").getenv("EMBEDDING_MODEL", "text-embedding-3-small")
            emb = self.ms.openai_client.embeddings.create(
                model=model,
                input=(text or "")[:2000],
            )
            return list(emb.data[0].embedding)
        except Exception as e:
            logger.warning("embed failed: %s", e)
            return None

    def _rank_score(
        self,
        *,
        vector_sim: float,
        type_match: float,
        importance: float,
        recency: float,
        graph_conf: float,
        source: str,
    ) -> float:
        # weighted blend
        score = (
            0.40 * vector_sim
            + 0.20 * type_match
            + 0.15 * importance
            + 0.15 * recency
            + 0.10 * graph_conf
        )
        if source == "typed_keyword_fallback":
            score *= 0.85  # slight penalty vs real embedding
        return max(0.0, min(1.0, score))

    async def retrieve(
        self,
        query: str,
        *,
        conversation_id: str,
        user_id: str = "default_user",
        memory_types: Optional[Sequence[str]] = None,
        limit: int = 5,
        include_v1_conversation: bool = True,
    ) -> Dict[str, Any]:
        types = list(memory_types) if memory_types else self.infer_types(query)
        results: List[Dict[str, Any]] = []
        fallback_used = False

        # 1) V1 conversation recall
        if include_v1_conversation and self.ms is not None:
            try:
                v1_text = await self.ms.recall_memories(
                    user_message=query,
                    conversation_id=conversation_id,
                    user_id=user_id,
                )
                if v1_text:
                    results.append(
                        {
                            "memory_type": V1_CONVERSATION_TYPE,
                            "source": "v1_recall",
                            "content": v1_text,
                            "score": 0.75,
                            "id": None,
                            "vector_sim": 0.0,
                            "type_match": 0.5,
                            "importance": 0.5,
                            "recency": 0.5,
                            "graph_conf": 0.0,
                        }
                    )
            except Exception as e:
                logger.warning("v1 recall failed: %s", e)

        # 2) Embedding search on typed rows
        query_vec = self._embed(query)
        typed = await self._fetch_typed_embedding(
            query=query,
            query_vec=query_vec,
            conversation_id=conversation_id,
            user_id=user_id,
            types=types,
            limit=limit * 3,
        )
        for it in typed:
            if it.get("source") == "typed_keyword_fallback":
                fallback_used = True
        results.extend(typed)

        # 3) Graph expansion by memory_id
        graph_hits: List[Dict[str, Any]] = []
        expanded: List[Dict[str, Any]] = []
        if self.graph is not None:
            for it in list(results):
                mid = it.get("id")
                if mid is None:
                    continue
                try:
                    for edge in self.graph.get_neighbors(str(mid), limit=5):
                        graph_hits.append(edge)
                        other = (
                            edge.get("target_memory_id")
                            if str(edge.get("source_memory_id")) == str(mid)
                            else edge.get("source_memory_id")
                        )
                        gconf = float(edge.get("confidence") or 0.5)
                        if other:
                            expanded.append(
                                {
                                    "memory_type": "graph",
                                    "source": "graph_expansion",
                                    "content": f"related_memory:{other} via {edge.get('relation')}",
                                    "score": self._rank_score(
                                        vector_sim=0.2,
                                        type_match=0.3,
                                        importance=0.3,
                                        recency=0.3,
                                        graph_conf=gconf,
                                        source="graph_expansion",
                                    ),
                                    "id": other,
                                    "vector_sim": 0.2,
                                    "type_match": 0.3,
                                    "importance": 0.3,
                                    "recency": 0.3,
                                    "graph_conf": gconf,
                                }
                            )
                except Exception as e:
                    logger.warning("graph expand failed: %s", e)
        results.extend(expanded)

        # 4) Rank
        results.sort(key=lambda x: float(x.get("score") or 0), reverse=True)
        seen = set()
        ranked = []
        for it in results:
            key = str(it.get("id") or "") + "|" + (it.get("content") or "")[:80]
            if key in seen:
                continue
            seen.add(key)
            ranked.append(it)

        formatted = self._format(ranked, limit=limit)
        return {
            "query": query,
            "types": types,
            "items": ranked[: limit * 2],
            "formatted": formatted,
            "graph_edges": graph_hits[:20],
            "used_embedding": query_vec is not None,
            "fallback_used": fallback_used,
            "fallback_source": "typed_keyword_fallback" if fallback_used else None,
        }

    async def _fetch_typed_embedding(
        self,
        *,
        query: str,
        query_vec: Optional[List[float]],
        conversation_id: str,
        user_id: str,
        types: List[str],
        limit: int,
    ) -> List[Dict[str, Any]]:
        if self.ms is None or not getattr(self.ms, "supabase", None):
            return []
        out: List[Dict[str, Any]] = []
        table = getattr(self.ms, "memories_table", "xiaochenguang_memories")
        now_ts = datetime.now(timezone.utc).timestamp()
        for mt in types:
            if mt not in MEMORY_TYPES:
                continue
            try:
                q = (
                    self.ms.supabase.table(table)
                    .select(
                        "id, user_message, assistant_message, document_content, "
                        "memory_type, importance_score, conversation_id, user_id, "
                        "embedding, created_at"
                    )
                    .eq("memory_type", mt)
                    .limit(max(limit, 10))
                )
                # isolation: always filter user_id when provided
                if user_id:
                    q = q.eq("user_id", user_id)
                result = q.execute()
                for row in result.data or []:
                    # double-check isolation
                    if user_id and row.get("user_id") and row.get("user_id") != user_id:
                        continue
                    blob = (
                        f"{row.get('user_message','')} "
                        f"{row.get('assistant_message','')} "
                        f"{row.get('document_content','')}"
                    )
                    row_emb = row.get("embedding")
                    vector_sim = 0.0
                    source = "typed_keyword_fallback"
                    if query_vec is not None and isinstance(row_emb, list) and row_emb:
                        try:
                            vector_sim = _cosine(query_vec, [float(x) for x in row_emb])
                            source = "typed_embedding"
                        except Exception:
                            source = "typed_keyword_fallback"
                    if source == "typed_keyword_fallback":
                        kw = 0.0
                        for w in (query or "").lower().split():
                            if w and w in blob.lower():
                                kw += 0.12
                        vector_sim = min(kw, 0.7)

                    type_match = 1.0 if row.get("memory_type") in types else 0.3
                    # prefer primary inferred type
                    if types and row.get("memory_type") == types[0]:
                        type_match = 1.0
                    elif row.get("memory_type") in types:
                        type_match = 0.75

                    try:
                        importance = float(row.get("importance_score") or 0.5)
                    except (TypeError, ValueError):
                        importance = 0.5
                    importance = max(0.0, min(1.0, importance))

                    created_ts = _parse_ts(row.get("created_at"))
                    if created_ts > 0:
                        age_days = max(0.0, (now_ts - created_ts) / 86400.0)
                        recency = max(0.0, 1.0 - min(age_days / 30.0, 1.0))
                    else:
                        recency = 0.4

                    emb_status = "ready" if source == "typed_embedding" else "missing"
                    try:
                        import json as _json
                        dc = row.get("document_content")
                        if isinstance(dc, str) and dc.startswith("{"):
                            meta = _json.loads(dc)
                            emb_status = meta.get("embedding_status") or emb_status
                    except Exception:
                        pass

                    score = self._rank_score(
                        vector_sim=vector_sim,
                        type_match=type_match,
                        importance=importance,
                        recency=recency,
                        graph_conf=0.0,
                        source=source,
                    )
                    out.append(
                        {
                            "memory_type": mt,
                            "source": source,
                            "content": blob.strip()[:500],
                            "score": score,
                            "id": row.get("id"),
                            "importance": importance,
                            "vector_sim": vector_sim,
                            "type_match": type_match,
                            "recency": recency,
                            "graph_conf": 0.0,
                            "embedding_status": emb_status,
                        }
                    )
            except Exception as e:
                logger.warning("typed embed fetch %s failed: %s", mt, e)
        out.sort(key=lambda x: x.get("score", 0), reverse=True)
        return out[:limit]

    def _format(self, items: List[Dict[str, Any]], limit: int = 5) -> str:
        if not items:
            return ""
        lines = ["【V2 記憶檢索】"]
        n = 0
        for it in items:
            if n >= limit:
                break
            mt = it.get("memory_type") or "?"
            content = (it.get("content") or "").strip()
            if not content:
                continue
            src = it.get("source") or ""
            snippet = content if len(content) < 400 else content[:400] + "…"
            lines.append(f"- [{mt}|{src}] {snippet}")
            n += 1
        return "\n".join(lines) if n else ""
