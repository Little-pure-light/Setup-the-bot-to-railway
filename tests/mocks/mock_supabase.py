"""Supabase 假客戶端（記憶體內表）。"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional


class MockQuery:
    def __init__(self, table: "MockTable", action: str = "select"):
        self.table = table
        self.action = action
        self._filters: List[tuple] = []
        self._data: Any = None
        self._limit: Optional[int] = None
        self._order: Optional[tuple] = None
        self._columns = "*"

    def select(self, *columns, **kwargs):
        self.action = "select"
        if columns:
            self._columns = columns[0] if len(columns) == 1 else ", ".join(str(c) for c in columns)
        elif "columns" in kwargs:
            self._columns = kwargs["columns"]
        else:
            self._columns = "*"
        return self

    def insert(self, data: Any):
        self.action = "insert"
        self._data = data
        return self

    def update(self, data: Dict[str, Any]):
        self.action = "update"
        self._data = data
        return self

    def delete(self):
        self.action = "delete"
        return self

    def eq(self, key: str, value: Any):
        self._filters.append(("eq", key, value))
        return self

    def order(self, key: str, desc: bool = False):
        self._order = (key, desc)
        return self

    def limit(self, n: int):
        self._limit = n
        return self

    def execute(self):
        rows = list(self.table.rows)

        def match(row: dict) -> bool:
            for op, k, v in self._filters:
                if op == "eq" and row.get(k) != v:
                    return False
            return True

        matched = [r for r in rows if match(r)]

        if self.action == "select":
            if self._order:
                key, desc = self._order
                matched.sort(key=lambda r: r.get(key) or "", reverse=desc)
            if self._limit is not None:
                matched = matched[: self._limit]
            return MockResult(deepcopy(matched))

        if self.action == "insert":
            payload = self._data
            items = payload if isinstance(payload, list) else [payload]
            inserted = []
            for item in items:
                row = dict(item)
                if "id" not in row:
                    row["id"] = self.table.next_id()
                self.table.rows.append(row)
                inserted.append(row)
            return MockResult(deepcopy(inserted))

        if self.action == "update":
            updated = []
            for row in matched:
                row.update(self._data or {})
                updated.append(deepcopy(row))
            return MockResult(updated)

        if self.action == "delete":
            keep = [r for r in self.table.rows if not match(r)]
            deleted = [r for r in self.table.rows if match(r)]
            self.table.rows = keep
            return MockResult(deepcopy(deleted))

        return MockResult([])


class MockResult:
    def __init__(self, data: List[Dict[str, Any]]):
        self.data = data


class MockTable:
    def __init__(self, name: str):
        self.name = name
        self.rows: List[Dict[str, Any]] = []
        self._id = 1

    def next_id(self) -> int:
        n = self._id
        self._id += 1
        return n

    def select(self, *columns):
        cols = "*"
        if columns:
            cols = columns[0] if len(columns) == 1 else ", ".join(str(c) for c in columns)
        return MockQuery(self, "select").select(cols)

    def insert(self, data: Any):
        return MockQuery(self, "insert").insert(data)

    def update(self, data: Dict[str, Any]):
        return MockQuery(self, "update").update(data)

    def delete(self):
        return MockQuery(self, "delete").delete()


class MockSupabase:
    def __init__(self):
        self._tables: Dict[str, MockTable] = {}

    def table(self, name: str) -> MockTable:
        if name not in self._tables:
            self._tables[name] = MockTable(name)
        return self._tables[name]

    def rpc(self, name: str, params: Optional[dict] = None):
        params = params or {}
        parent = self

        class _Rpc:
            def execute(self_inner):
                # Task006: simulate match_memories / match_memories_v2 isolation filters
                if name in ("match_memories", "match_memories_v2"):
                    table = parent.table("xiaochenguang_memories")
                    rows = [
                        r for r in table.rows
                        if r.get("memory_type", "conversation") == "conversation"
                    ]
                    if name == "match_memories":
                        conv = params.get("conversation_id")
                        if conv is not None:
                            rows = [r for r in rows if r.get("conversation_id") == conv]
                    else:
                        f_conv = params.get("filter_conversation_id")
                        f_user = params.get("filter_user_id")
                        f_ai = params.get("filter_ai_id")
                        if f_conv:
                            rows = [r for r in rows if r.get("conversation_id") == f_conv]
                        if f_user and f_user not in ("", "default_user"):
                            rows = [r for r in rows if r.get("user_id") == f_user]
                        if f_ai:
                            rows = [r for r in rows if r.get("ai_id") == f_ai]
                    limit = int(params.get("match_count") or 3)
                    out = []
                    for r in rows[:limit]:
                        out.append({
                            "user_message": r.get("user_message"),
                            "assistant_message": r.get("assistant_message"),
                            "created_at": r.get("created_at"),
                            "similarity": 0.9,
                            "conversation_id": r.get("conversation_id"),
                            "user_id": r.get("user_id"),
                            "ai_id": r.get("ai_id"),
                        })
                    return MockResult(out)
                return MockResult([])

        return _Rpc()
