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
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from backend.modules.memory_types import MEMORY_TYPES, V1_CONVERSATION_TYPE

logger = logging.getLogger("memory.retrieval")


def _legacy_ai_default() -> str:
    """The single historical AI these legacy rows belonged to before ai_id existed."""
    return (os.getenv("AI_ID", "xiaochenguang_v1") or "xiaochenguang_v1").strip()


def _ai_match(row_ai: Any, requested_ai: Optional[str]) -> bool:
    """Owner (ai) match with legacy-NULL compatibility.

    Task 006 (PR18 review round 2, P0): keep BOTH invariants —
      1. Never leak across an EXPLICIT different ai_id.
      2. Existing legit single-AI memories (ai_id NULL/empty, pre-migration)
         remain retrievable — but ONLY for the legacy default AI.
    A row with no ai_id is treated as belonging to the legacy default AI; a
    request for any OTHER explicit AI must NOT see it. user_id is enforced
    strictly by the caller (this only decides the ai dimension).
    """
    ra = str(row_ai).strip() if row_ai is not None else ""
    req = str(requested_ai or "").strip()
    if not ra:
        # legacy row without ai_id → belongs to the historical/default AI only
        return bool(req) and req == _legacy_ai_default()
    return ra == req

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

    # Quality stage weights: prioritize relevance + importance over bare recency
    # (avoid old-but-unimportant beating true matches)
    RANK_W_VECTOR = 0.36
    RANK_W_IMPORTANCE = 0.20
    RANK_W_TYPE = 0.16
    RANK_W_GRAPH = 0.16
    RANK_W_RECENCY = 0.12

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
        score = (
            self.RANK_W_VECTOR * vector_sim
            + self.RANK_W_IMPORTANCE * importance
            + self.RANK_W_TYPE * type_match
            + self.RANK_W_GRAPH * graph_conf
            + self.RANK_W_RECENCY * recency
        )
        if source == "typed_keyword_fallback":
            score *= 0.82
        if source == "graph_expansion":
            # graph edges must contribute, but not dominate pure semantic hits
            score = max(score, 0.25 + 0.55 * graph_conf + 0.15 * importance)
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
        ai_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        types = list(memory_types) if memory_types else self.infer_types(query)
        results: List[Dict[str, Any]] = []
        fallback_used = False
        resolved_ai = (ai_id or __import__("os").getenv("AI_ID", "xiaochenguang_v1") or "").strip()

        # 1) V1 conversation recall (must pass ai_id for multi-AI isolation)
        if include_v1_conversation and self.ms is not None:
            try:
                v1_text = await self.ms.recall_memories(
                    user_message=query,
                    conversation_id=conversation_id,
                    user_id=user_id,
                    ai_id=resolved_ai or None,
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
            ai_id=resolved_ai or None,
        )
        for it in typed:
            if it.get("source") == "typed_keyword_fallback":
                fallback_used = True
        results.extend(typed)

        # 3) Graph expansion by memory_id — load neighbor content when possible
        graph_hits: List[Dict[str, Any]] = []
        expanded: List[Dict[str, Any]] = []
        graph_used = False
        if self.graph is not None:
            seed_ids = [str(it.get("id")) for it in results if it.get("id") is not None][
                :8
            ]
            neighbor_ids: List[str] = []
            edge_by_neighbor: Dict[str, Dict[str, Any]] = {}
            for mid in seed_ids:
                try:
                    for edge in self.graph.get_neighbors(str(mid), limit=6):
                        graph_hits.append(edge)
                        other = (
                            edge.get("target_memory_id")
                            if str(edge.get("source_memory_id")) == str(mid)
                            else edge.get("source_memory_id")
                        )
                        if not other or str(other) == str(mid):
                            continue
                        other = str(other)
                        gconf = float(edge.get("confidence") or 0.5)
                        # keep strongest edge per neighbor
                        prev = edge_by_neighbor.get(other)
                        if prev is None or gconf > float(prev.get("confidence") or 0):
                            edge_by_neighbor[other] = edge
                            if other not in neighbor_ids:
                                neighbor_ids.append(other)
                except Exception as e:
                    logger.warning("graph expand failed: %s", e)

            # hydrate neighbor content from store (graph utilization)
            hydrated = await self._hydrate_memories_by_ids(
                neighbor_ids[:12], user_id=user_id, ai_id=resolved_ai or None
            )
            for other, row in hydrated.items():
                edge = edge_by_neighbor.get(other) or {}
                gconf = float(edge.get("confidence") or 0.5)
                rel = edge.get("relation") or "related"
                blob = (
                    f"{row.get('user_message') or ''} "
                    f"{row.get('assistant_message') or ''} "
                    f"{row.get('document_content') or ''}"
                ).strip()
                if not blob:
                    blob = f"related_memory:{other} via {rel}"
                try:
                    importance = float(row.get("importance_score") or 0.55)
                except (TypeError, ValueError):
                    importance = 0.55
                mt = row.get("memory_type") or "graph"
                type_match = 1.0 if mt in types else 0.45
                item = {
                    "memory_type": mt if mt in MEMORY_TYPES else "graph",
                    "source": "graph_expansion",
                    "content": blob[:500],
                    "id": other,
                    "importance": importance,
                    "vector_sim": 0.25,
                    "type_match": type_match,
                    "recency": 0.45,
                    "graph_conf": gconf,
                    "graph_relation": rel,
                    "via_graph": True,
                }
                item["score"] = self._rank_score(
                    vector_sim=item["vector_sim"],
                    type_match=type_match,
                    importance=importance,
                    recency=0.45,
                    graph_conf=gconf,
                    source="graph_expansion",
                )
                expanded.append(item)
                graph_used = True

            # fallback stub edges if hydration empty but edges exist
            if not expanded:
                for other, edge in list(edge_by_neighbor.items())[:5]:
                    gconf = float(edge.get("confidence") or 0.5)
                    expanded.append(
                        {
                            "memory_type": "graph",
                            "source": "graph_expansion",
                            "content": f"related_memory:{other} via {edge.get('relation')}",
                            "score": self._rank_score(
                                vector_sim=0.15,
                                type_match=0.25,
                                importance=0.35,
                                recency=0.3,
                                graph_conf=gconf,
                                source="graph_expansion",
                            ),
                            "id": other,
                            "vector_sim": 0.15,
                            "type_match": 0.25,
                            "importance": 0.35,
                            "recency": 0.3,
                            "graph_conf": gconf,
                            "via_graph": True,
                        }
                    )
                    graph_used = True
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
            "used_graph": graph_used or bool(graph_hits),
            "graph_expanded_count": len(expanded),
            "fallback_used": fallback_used,
            "fallback_source": "typed_keyword_fallback" if fallback_used else None,
            "rank_weights": {
                "vector": self.RANK_W_VECTOR,
                "importance": self.RANK_W_IMPORTANCE,
                "type": self.RANK_W_TYPE,
                "graph": self.RANK_W_GRAPH,
                "recency": self.RANK_W_RECENCY,
            },
        }

    async def _hydrate_memories_by_ids(
        self, ids: List[str], *, user_id: str, ai_id: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """Fetch memory rows by id for graph expansion content (owner fail-closed)."""
        out: Dict[str, Dict[str, Any]] = {}
        if not ids or self.ms is None or not getattr(self.ms, "supabase", None):
            return out
        uid = (user_id or "").strip()
        if not uid:
            return out
        table = getattr(self.ms, "memories_table", "xiaochenguang_memories")
        for mid in ids:
            try:
                q = (
                    self.ms.supabase.table(table)
                    .select(
                        "id, user_message, assistant_message, document_content, "
                        "memory_type, importance_score, user_id, ai_id, created_at"
                    )
                    .eq("id", mid)
                    .eq("user_id", uid)
                    .limit(1)
                )
                # Do NOT .eq(ai_id) at query level (would drop legacy NULL rows).
                # Fetch by strict user_id, then apply legacy-aware ai match.
                result = q.execute()
                rows = result.data or []
                if rows and _ai_match(rows[0].get("ai_id"), ai_id):
                    out[str(mid)] = rows[0]
            except Exception as e:
                logger.warning("hydrate memory %s failed: %s", mid, e)
        return out

    _TYPED_SELECT = (
        "id, user_message, assistant_message, document_content, "
        "memory_type, importance_score, conversation_id, user_id, "
        "ai_id, embedding, created_at"
    )

    def _owner_scoped_rows(
        self, table: str, select_cols: str, *, mt: str, uid: str,
        requested_ai: str, per_query_limit: int,
    ) -> List[Dict[str, Any]]:
        """Owner-scoped fetch that filters ai_id at the DATABASE level to avoid
        cross-AI query-limit starvation (PR18 review round 3, P1-A).

        - Query 1: exact ai_id match in SQL (other AIs never take limit slots).
        - Query 2: only when requested_ai is the legacy default — a SECOND
          bounded query for legacy rows whose ai_id IS NULL.
        user_id is always enforced in SQL. Rows are de-duplicated.
        """
        sb = self.ms.supabase
        seen: set = set()
        combined: List[Dict[str, Any]] = []

        def _collect(rows: Optional[List[Dict[str, Any]]]) -> None:
            for r in rows or []:
                if r.get("user_id") != uid:
                    continue
                key = r.get("id")
                if key is None:
                    key = id(r)
                if key in seen:
                    continue
                seen.add(key)
                combined.append(r)

        # 1) explicit ai match at DB level
        try:
            q1 = (
                sb.table(table).select(select_cols)
                .eq("memory_type", mt).eq("user_id", uid).eq("ai_id", requested_ai)
                .limit(per_query_limit)
            )
            _collect(q1.execute().data)
        except Exception as e:
            logger.warning("owner rows q1 failed (%s): %s", mt, e)

        # 2) legacy NULL ai rows, ONLY when the requested ai is the legacy default
        if requested_ai == _legacy_ai_default():
            try:
                q2 = (
                    sb.table(table).select(select_cols)
                    .eq("memory_type", mt).eq("user_id", uid).is_("ai_id", "null")
                    .limit(per_query_limit)
                )
                _collect(q2.execute().data)
            except Exception as e:
                logger.warning("owner rows q2 legacy-null failed (%s): %s", mt, e)

        return combined

    async def _fetch_typed_embedding(
        self,
        *,
        query: str,
        query_vec: Optional[List[float]],
        conversation_id: str,
        user_id: str,
        types: List[str],
        limit: int,
        ai_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if self.ms is None or not getattr(self.ms, "supabase", None):
            return []
        uid = (user_id or "").strip()
        if not uid:
            return []
        req = (ai_id or "").strip() or _legacy_ai_default()
        out: List[Dict[str, Any]] = []
        table = getattr(self.ms, "memories_table", "xiaochenguang_memories")
        now_ts = datetime.now(timezone.utc).timestamp()
        for mt in types:
            if mt not in MEMORY_TYPES:
                continue
            try:
                rows = self._owner_scoped_rows(
                    table, self._TYPED_SELECT, mt=mt, uid=uid,
                    requested_ai=req, per_query_limit=max(limit, 10),
                )
                for row in rows:
                    # fail-closed isolation double-check (user strict; ai legacy-aware)
                    if row.get("user_id") != uid:
                        continue
                    if not _ai_match(row.get("ai_id"), req):
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
