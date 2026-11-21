#!/usr/bin/env python3
"""章节快照备份：正文 + 设定 + 摘要 + 记忆 + 状态 + commit。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from novel_creation_promax.core import workspace_confirmation as wc  # noqa: E402
from novel_creation_promax.core.chapter_backup import list_snapshots, snapshot_chapter  # noqa: E402


def _workspace_for(novel_dir: Path) -> Path | None:
    parts = novel_dir.resolve().parts
    if "novel_output" not in parts:
        return None
    index = parts.index("novel_output")
    return Path(*parts[:index])


def main() -> int:
    parser = argparse.ArgumentParser(description="章节快照备份")
    sub = parser.add_subparsers(dest="command", required=True)

    snap = sub.add_parser("snapshot", help="备份一章")
    snap.add_argument("--novel-dir", required=True)
    snap.add_argument("--chapter", type=int, required=True)
    snap.add_argument("--reason", default="")
    snap.add_argument("--keep", type=int, default=5, help="每章保留最近 N 份；0 表示不清理")
    snap.add_argument("--json", action="store_true")

    list_parser = sub.add_parser("list", help="列出快照")
    list_parser.add_argument("--novel-dir", required=True)
    list_parser.add_argument("--chapter", type=int, default=0)
    list_parser.add_argument("--json", action="store_true")

    args = parser.parse_args()
    novel_dir = Path(args.novel_dir).expanduser().resolve()

    if args.command == "list":
        rows = list_snapshots(novel_dir, args.chapter or None)
        if args.json:
            print(json.dumps({"snapshots": rows}, ensure_ascii=False, indent=2))
        else:
            if not rows:
                print("没有快照")
            for row in rows:
                print(
                    f"{row['created_at']} | 第{row['chapter']}章 | "
                    f"{row['files']} 个文件 | {Path(row['path']).name} | {row['reason']}"
                )
        return 0

    workspace = _workspace_for(novel_dir)
    if workspace is not None:
        try:
            wc.require_confirmed(workspace)
        except wc.WorkspaceConfirmationError as exc:
            print(f"[ERROR] {exc}", file=sys.stderr)
            return 2

    try:
        summary = snapshot_chapter(
            novel_dir,
            args.chapter,
            reason=args.reason,
            keep=args.keep,
        )
    except (OSError, ValueError) as exc:
        print(f"[ERROR] 备份失败: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"[OK] 已备份第{args.chapter}章: {summary['path']}")
        print(f"     文件数: {summary['files']}")
        if summary["pruned"]:
            print(f"     已清理旧快照: {', '.join(summary['pruned'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
