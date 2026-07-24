#!/usr/bin/env python3
"""
Memory System V2 — migration helper (non-destructive).

- Does NOT drop or rewrite V1 conversation rows.
- Prints SQL optional helpers for Supabase.
- Optionally smoke-checks MEMORY_V2_ENABLED factory.

Usage:
  python scripts/migrate_memory_v2.py --print-sql
  python scripts/migrate_memory_v2.py --self-check
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SQL = r"""
-- Memory System V2 (optional SQL) — run manually in Supabase SQL editor.
-- Safe: does not modify existing conversation rows.

-- 1) Allow V2 memory_type values (if you use a CHECK constraint, relax it).
-- ALTER TABLE xiaochenguang_memories DROP CONSTRAINT IF EXISTS memories_memory_type_check;

-- 2) Helpful indexes for typed retrieval
CREATE INDEX IF NOT EXISTS idx_memories_type_user
  ON xiaochenguang_memories (memory_type, user_id);

CREATE INDEX IF NOT EXISTS idx_memories_type_conv
  ON xiaochenguang_memories (memory_type, conversation_id);

-- 3) Optional comment
COMMENT ON COLUMN xiaochenguang_memories.memory_type IS
  'conversation (V1) | episodic|semantic|identity|emotion|reflection|transformation|attention|causal (V2)';
"""


def main():
    parser = argparse.ArgumentParser(description="Memory V2 migration helper")
    parser.add_argument("--print-sql", action="store_true", help="Print optional SQL")
    parser.add_argument("--self-check", action="store_true", help="Import V2 modules")
    args = parser.parse_args()

    if args.print_sql or not (args.self_check):
        print(SQL)

    if args.self_check:
        from backend.modules.memory_classifier import MemoryClassifier
        from backend.modules.memory_manager import MemoryManager, memory_v2_enabled
        from backend.modules.retrieval_engine import RetrievalEngine
        from backend.modules.graph_manager import GraphManager
        from backend.modules.night_growth import NightGrowth

        clf = MemoryClassifier()
        r = clf.classify(
            conversation={"user_message": "你是誰？", "assistant_message": "我是小宸光"}
        )
        assert r.memory_type == "identity", r
        g = GraphManager(user_id="migrate_check")
        g.clear()
        e = g.add_edge("a", "b", "supports")
        assert e["relation"] == "supports"
        print("self-check OK")
        print("MEMORY_V2_ENABLED =", memory_v2_enabled())
        print("modules importable: MemoryManager, RetrievalEngine, NightGrowth")


if __name__ == "__main__":
    main()
