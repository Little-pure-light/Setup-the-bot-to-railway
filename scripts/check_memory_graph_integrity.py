#!/usr/bin/env python3
"""
Check Memory Graph integrity.

Usage:
  python scripts/check_memory_graph_integrity.py
  python scripts/check_memory_graph_integrity.py --user-id default_user
  python scripts/check_memory_graph_integrity.py --graph-file data/memory_graph.json

Exit code 0 if ok, 1 if issues found.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# project root on path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.modules.graph_manager import GraphManager  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Memory graph integrity check")
    parser.add_argument("--user-id", default="default_user")
    parser.add_argument(
        "--graph-file",
        default=None,
        help="Path to memory_graph.json (default: MEMORY_GRAPH_FILE or data/memory_graph.json)",
    )
    parser.add_argument(
        "--all-users",
        action="store_true",
        help="Scan all user keys in graph file",
    )
    args = parser.parse_args()

    storage = args.graph_file
    if storage is None:
        storage = str(ROOT / "data" / "memory_graph.json")

    results = []
    if args.all_users and Path(storage).exists():
        try:
            raw = json.loads(Path(storage).read_text(encoding="utf-8"))
            user_ids = list(raw.keys()) if isinstance(raw, dict) else [args.user_id]
        except Exception:
            user_ids = [args.user_id]
    else:
        user_ids = [args.user_id]

    overall_ok = True
    for uid in user_ids:
        g = GraphManager(user_id=uid, storage_path=storage)
        report = g.integrity_check()
        results.append(report)
        if not report.get("ok"):
            overall_ok = False

    summary = {
        "users_checked": len(results),
        "results": results,
        "ok": overall_ok,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
