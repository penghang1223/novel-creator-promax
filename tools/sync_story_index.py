#!/usr/bin/env python3
"""Build or refresh the SQLite story read model."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from novel_creation_promax.core.story_index import (  # noqa: E402
    index_path,
    query_projects,
    sync_root_index,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="同步小说项目 SQLite 读模型")
    parser.add_argument("--root", default=str(PROJECT_ROOT), help="项目根目录")
    parser.add_argument("--output-root", default="", help="小说输出目录，默认 <root>/novel_output")
    parser.add_argument("--json", action="store_true", help="打印完整 JSON 结果")
    parser.add_argument("--check", action="store_true", help="只检查索引是否存在，不执行同步")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    db_path = index_path(root)
    if args.check:
        payload = {"path": str(db_path), "exists": db_path.is_file()}
    else:
        output_root = Path(args.output_root).resolve() if args.output_root else None
        payload = sync_root_index(root, output_root=output_root)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"[OK] story index: {payload.get('path', db_path)}")
        if "projects" in payload:
            print(f"[OK] projects={payload['projects']} chapters={payload['chapters']}")
        elif not payload.get("exists"):
            print("[WARN] 索引不存在，请先执行不带 --check 的同步")
    return 0 if payload.get("exists", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
