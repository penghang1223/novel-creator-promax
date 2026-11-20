#!/usr/bin/env python3
"""Move historical knowledge subtrees into knowledge_base/90_Archive safely."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

MIGRATIONS = (
    (
        Path("knowledge_base/15_Ideas/惊鸿归档"),
        Path("knowledge_base/90_Archive/惊鸿归档"),
    ),
    (
        Path("knowledge_base/40_Writing/写作技巧"),
        Path("knowledge_base/90_Archive/40_Writing_写作技巧"),
    ),
)


def describe(source: Path, target: Path) -> dict:
    files = [path for path in source.rglob("*") if path.is_file()] if source.is_dir() else []
    return {
        "source": source.as_posix(),
        "target": target.as_posix(),
        "source_exists": source.is_dir(),
        "target_exists": target.exists(),
        "file_count": len(files),
        "size_bytes": sum(path.stat().st_size for path in files),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="归档知识库历史目录，默认 dry-run")
    parser.add_argument("--apply", action="store_true", help="实际移动目录")
    args = parser.parse_args()

    plans = [describe(PROJECT_ROOT / source, PROJECT_ROOT / target) for source, target in MIGRATIONS]
    invalid = [
        item for item in plans
        if item["source_exists"] and item["target_exists"]
    ]
    for item in plans:
        state = "ready"
        if not item["source_exists"]:
            state = "already-archived"
        elif item["target_exists"]:
            state = "blocked-target-exists"
        print(
            f"[{state}] {item['source']} -> {item['target']} "
            f"({item['file_count']} files, {item['size_bytes']} bytes)"
        )

    if invalid:
        blocked = [item for item in invalid if item["target_exists"]]
        if blocked:
            print("[FATAL] 目标目录已存在，拒绝覆盖。")
            return 2

    if not args.apply:
        print("[dry-run] 未移动；加 --apply 才会执行。")
        return 0

    for source, target in MIGRATIONS:
        source_path = PROJECT_ROOT / source
        target_path = PROJECT_ROOT / target
        if not source_path.is_dir():
            continue
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source_path), str(target_path))
        print(f"[moved] {source} -> {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
