"""
GraphManager — memory relation graph (Phase 2 + Fix integrity).

Nodes MUST be memory_id (stringified).
Forbidden as node ids: bare labels like "reflection", "document", "emotion".

Edge schema:
  source_memory_id, target_memory_id, relation, confidence,
  created_at, created_by, metadata (+ timestamp for legacy)
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from backend.modules.memory_types import GRAPH_RELATIONS

logger = logging.getLogger("memory.graph")

_FORBIDDEN_NODE_LABELS = frozenset(
    {
        "reflection",
        "document",
        "emotion",
        "tool",
        "hint",
        "semantic",
        "identity",
        "episodic",
        "causal",
        "attention",
        "transformation",
    }
)


def _is_valid_memory_node(node_id: str) -> bool:
    nid = str(node_id or "").strip()
    if not nid:
        return False
    low = nid.lower()
    if low in _FORBIDDEN_NODE_LABELS:
        return False
    if low.startswith("hint:"):
        return False
    return True


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class GraphManager:
    def __init__(
        self,
        redis_interface=None,
        *,
        user_id: str = "default_user",
        storage_path: Optional[str] = None,
    ):
        self.redis = redis_interface
        self.user_id = user_id or "default_user"
        default_path = (
            Path(__file__).resolve().parents[2] / "data" / "memory_graph.json"
        )
        self.storage_path = Path(
            storage_path or os.getenv("MEMORY_GRAPH_FILE", str(default_path))
        )
        self._local_edges: List[Dict[str, Any]] = []
        self._loaded = False

    def _redis_key(self) -> str:
        return f"memory_graph:{self.user_id}:edges"

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        try:
            if self.redis and getattr(self.redis, "redis", None):
                raw = self.redis.redis.get(self._redis_key())
                if raw:
                    if isinstance(raw, bytes):
                        raw = raw.decode("utf-8")
                    data = json.loads(raw)
                    if isinstance(data, list):
                        self._local_edges = [self._normalize_edge(e) for e in data if e]
                        return
        except Exception as e:
            logger.warning("graph redis load failed: %s", e)
        try:
            if self.storage_path.exists():
                all_data = json.loads(self.storage_path.read_text(encoding="utf-8"))
                if isinstance(all_data, dict):
                    raw_list = list(all_data.get(self.user_id) or [])
                elif isinstance(all_data, list):
                    raw_list = all_data
                else:
                    raw_list = []
                self._local_edges = [self._normalize_edge(e) for e in raw_list if e]
        except Exception as e:
            logger.warning("graph file load failed: %s", e)

    def _normalize_edge(self, e: Dict[str, Any]) -> Dict[str, Any]:
        e = dict(e or {})
        src = e.get("source_memory_id") or e.get("source_id")
        tgt = e.get("target_memory_id") or e.get("target_id")
        e["source_memory_id"] = str(src) if src is not None else ""
        e["target_memory_id"] = str(tgt) if tgt is not None else ""
        e["source_id"] = e["source_memory_id"]
        e["target_id"] = e["target_memory_id"]
        if "confidence" not in e:
            e["confidence"] = float((e.get("meta") or {}).get("confidence") or 0.5)
        ts = e.get("timestamp") or e.get("ts") or time.time()
        e["timestamp"] = ts
        e["ts"] = ts
        if not e.get("created_at"):
            try:
                e["created_at"] = datetime.fromtimestamp(
                    float(ts), tz=timezone.utc
                ).isoformat()
            except Exception:
                e["created_at"] = _iso_now()
        if "created_by" not in e:
            e["created_by"] = (e.get("meta") or {}).get("created_by") or "system"
        # metadata preferred; keep meta as alias
        meta = e.get("metadata") or e.get("meta") or {}
        e["metadata"] = dict(meta)
        e["meta"] = e["metadata"]
        if "id" not in e or not e["id"]:
            e["id"] = str(uuid.uuid4())
        return e

    def _persist(self) -> None:
        try:
            if self.redis and getattr(self.redis, "redis", None):
                self.redis.redis.set(
                    self._redis_key(),
                    json.dumps(self._local_edges, ensure_ascii=False),
                )
        except Exception as e:
            logger.warning("graph redis save failed: %s", e)
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            existing: Dict[str, Any] = {}
            if self.storage_path.exists():
                try:
                    raw = json.loads(self.storage_path.read_text(encoding="utf-8"))
                    if isinstance(raw, dict):
                        existing = raw
                except Exception:
                    existing = {}
            existing[self.user_id] = self._local_edges
            self.storage_path.write_text(
                json.dumps(existing, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning("graph file save failed: %s", e)

    def add_edge(
        self,
        source_memory_id: str,
        target_memory_id: str,
        relation: str,
        *,
        confidence: float = 0.5,
        meta: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        created_by: str = "system",
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
        allow_duplicate: bool = False,
    ) -> Dict[str, Any]:
        self._ensure_loaded()
        src = str(source_memory_id or source_id or "").strip()
        tgt = str(target_memory_id or target_id or "").strip()
        if not _is_valid_memory_node(src) or not _is_valid_memory_node(tgt):
            raise ValueError(
                f"nodes must be memory_id, not labels: {src!r} -> {tgt!r}"
            )
        if not src or not tgt:
            raise ValueError("source_memory_id and target_memory_id required")
        rel = (relation or "").strip().lower()
        if rel not in GRAPH_RELATIONS:
            raise ValueError(f"invalid relation: {relation}")
        conf = max(0.0, min(1.0, float(confidence)))
        md = dict(metadata or meta or {})
        if not allow_duplicate:
            for existing in self._local_edges:
                en = self._normalize_edge(existing)
                if (
                    en.get("source_memory_id") == src
                    and en.get("target_memory_id") == tgt
                    and en.get("relation") == rel
                    and not en.get("archived")
                ):
                    return en
        ts = time.time()
        edge = {
            "id": str(uuid.uuid4()),
            "source_memory_id": src,
            "target_memory_id": tgt,
            "source_id": src,
            "target_id": tgt,
            "relation": rel,
            "confidence": conf,
            "timestamp": ts,
            "ts": ts,
            "created_at": _iso_now(),
            "created_by": created_by or "system",
            "metadata": md,
            "meta": md,
            "user_id": self.user_id,
            "archived": False,
        }
        self._local_edges.append(edge)
        if len(self._local_edges) > 5000:
            self._local_edges = self._local_edges[-5000:]
        self._persist()
        return edge

    def get_neighbors(
        self,
        memory_id: str,
        *,
        relation: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        self._ensure_loaded()
        nid = str(memory_id)
        out = []
        for e in reversed(self._local_edges):
            e = self._normalize_edge(e)
            if e.get("archived"):
                continue
            if e.get("source_memory_id") != nid and e.get("target_memory_id") != nid:
                continue
            if relation and e.get("relation") != relation:
                continue
            out.append(e)
            if len(out) >= limit:
                break
        return out

    def list_edges(self, limit: int = 100, *, include_archived: bool = False) -> List[Dict[str, Any]]:
        self._ensure_loaded()
        edges = [self._normalize_edge(e) for e in self._local_edges]
        if not include_archived:
            edges = [e for e in edges if not e.get("archived")]
        return edges[-limit:]

    def archive_edges_for_memory(self, memory_id: str) -> int:
        """Soft-archive edges involving memory_id so they are not orphan live edges."""
        self._ensure_loaded()
        mid = str(memory_id)
        n = 0
        for e in self._local_edges:
            en = self._normalize_edge(e)
            if en.get("source_memory_id") == mid or en.get("target_memory_id") == mid:
                if not e.get("archived"):
                    e["archived"] = True
                    e["archived_at"] = _iso_now()
                    n += 1
        if n:
            self._persist()
        return n

    def remove_edges_for_memory(self, memory_id: str) -> int:
        """Hard-remove edges involving memory_id."""
        self._ensure_loaded()
        mid = str(memory_id)
        before = len(self._local_edges)
        self._local_edges = [
            e
            for e in self._local_edges
            if self._normalize_edge(e).get("source_memory_id") != mid
            and self._normalize_edge(e).get("target_memory_id") != mid
        ]
        removed = before - len(self._local_edges)
        if removed:
            self._persist()
        return removed

    def apply_classification_relations(
        self,
        memory_id: str,
        relations: List[Dict[str, Any]],
        *,
        related_memory_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        created = []
        mid = str(memory_id)
        if not _is_valid_memory_node(mid):
            return created
        related = [
            str(x) for x in (related_memory_ids or []) if _is_valid_memory_node(str(x))
        ]
        for rel in relations or []:
            name = (rel.get("relation") or "").lower()
            if name not in GRAPH_RELATIONS:
                continue
            src = rel.get("source_memory_id") or rel.get("source_id")
            tgt = rel.get("target_memory_id") or rel.get("target_id") or mid
            if src and _is_valid_memory_node(str(src)) and _is_valid_memory_node(str(tgt)):
                try:
                    created.append(
                        self.add_edge(
                            str(src),
                            str(tgt),
                            name,
                            confidence=float(rel.get("confidence") or 0.5),
                            created_by="classifier",
                            meta={
                                "memory_id": mid,
                                **{k: v for k, v in rel.items() if k != "relation"},
                            },
                        )
                    )
                except ValueError:
                    continue
                continue
            for other in related:
                if other == mid:
                    continue
                try:
                    created.append(
                        self.add_edge(
                            mid,
                            other,
                            name,
                            confidence=float(rel.get("confidence") or 0.4),
                            created_by="classifier",
                            meta={"via": "classification"},
                        )
                    )
                except ValueError:
                    continue
        return created

    def integrity_check(
        self,
        *,
        known_memory_ids: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        """
        Check graph integrity for current user.
        known_memory_ids: optional set of valid memory ids; if provided, missing ids reported.
        """
        self._ensure_loaded()
        nodes: Set[str] = set()
        orphan_edges = []
        invalid_relations = []
        missing_memory_ids = []
        invalid_nodes = []
        duplicate_keys: Dict[str, int] = {}
        duplicates = []
        active_edges = []

        for raw in self._local_edges:
            e = self._normalize_edge(raw)
            if e.get("archived"):
                continue
            active_edges.append(e)
            src = e.get("source_memory_id") or ""
            tgt = e.get("target_memory_id") or ""
            rel = e.get("relation") or ""
            if src:
                nodes.add(src)
            if tgt:
                nodes.add(tgt)
            if not src or not tgt:
                orphan_edges.append({"edge_id": e.get("id"), "reason": "empty_endpoint"})
            if not _is_valid_memory_node(src) or not _is_valid_memory_node(tgt):
                invalid_nodes.append({"edge_id": e.get("id"), "src": src, "tgt": tgt})
            if rel not in GRAPH_RELATIONS:
                invalid_relations.append({"edge_id": e.get("id"), "relation": rel})
            if known_memory_ids is not None:
                if src and src not in known_memory_ids:
                    missing_memory_ids.append(src)
                if tgt and tgt not in known_memory_ids:
                    missing_memory_ids.append(tgt)
            key = f"{src}|{tgt}|{rel}"
            duplicate_keys[key] = duplicate_keys.get(key, 0) + 1

        for key, count in duplicate_keys.items():
            if count > 1:
                duplicates.append({"key": key, "count": count})

        return {
            "user_id": self.user_id,
            "total_nodes": len(nodes),
            "total_edges": len(active_edges),
            "orphan_edges": orphan_edges,
            "orphan_edge_count": len(orphan_edges),
            "invalid_relations": invalid_relations,
            "invalid_relation_count": len(invalid_relations),
            "invalid_nodes": invalid_nodes,
            "invalid_node_count": len(invalid_nodes),
            "missing_memory_ids": sorted(set(missing_memory_ids)),
            "missing_memory_id_count": len(set(missing_memory_ids)),
            "duplicate_edges": duplicates,
            "duplicate_edge_count": len(duplicates),
            "ok": (
                len(orphan_edges) == 0
                and len(invalid_relations) == 0
                and len(invalid_nodes) == 0
                and len(duplicates) == 0
            ),
        }

    def clear(self) -> None:
        self._local_edges = []
        self._loaded = True
        self._persist()
