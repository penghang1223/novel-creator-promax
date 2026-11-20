#!/usr/bin/env python3
"""Build and query the rebuildable knowledge-base index."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from novel_creation_promax.core.knowledge_index import search_knowledge, sync_knowledge_index  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="索引并检索 knowledge_base")
    parser.add_argument("query", nargs="?", help="检索词；不提供时只同步索引")
    parser.add_argument("--root", default=str(PROJECT_ROOT), help="项目根目录")
    parser.add_argument("--limit", type=int, default=8, help="最多返回条数")
    parser.add_argument("--backend", choices=["bm25", "lexical", "tfidf"], default="bm25", help="检索后端")
    parser.add_argument("--sync-only", action="store_true", help="只同步索引")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    result = sync_knowledge_index(root)
    if args.sync_only or not args.query:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    print(json.dumps({"query": args.query, "backend": args.backend, "index": result, "results": search_knowledge(root, args.query, limit=args.limit, backend=args.backend)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
