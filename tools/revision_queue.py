#!/usr/bin/env python3
"""Create, inspect, approve, reject, and restore chapter revisions."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from novel_creation_promax.core.revision_control import (  # noqa: E402
    create_proposal,
    create_snapshot,
    list_proposals,
    restore_snapshot,
    review_proposal,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="章节 revision 快照与人工审批队列")
    parser.add_argument("command", choices=["snapshot", "propose", "list", "review", "restore"])
    parser.add_argument("--novel-dir", required=True)
    parser.add_argument("--chapter", type=int, required=True)
    parser.add_argument("--proposal-id", default="")
    parser.add_argument("--snapshot-id", default="")
    parser.add_argument("--content-file", default="", help="propose 使用的新正文文件")
    parser.add_argument("--reason", default="")
    parser.add_argument("--source", default="cli")
    parser.add_argument("--approve", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    novel_dir = Path(args.novel_dir).resolve()
    if args.command == "snapshot":
        result = create_snapshot(novel_dir, args.chapter, reason=args.reason or "手工快照", source=args.source)
    elif args.command == "propose":
        if not args.content_file:
            parser.error("propose 必须提供 --content-file")
        result = create_proposal(
            novel_dir,
            args.chapter,
            Path(args.content_file).read_text(encoding="utf-8"),
            reason=args.reason or "待审核修改",
            source=args.source,
        )
    elif args.command == "list":
        result = {"proposals": list_proposals(novel_dir, args.chapter)}
    elif args.command == "review":
        if not args.proposal_id:
            parser.error("review 必须提供 --proposal-id")
        result = review_proposal(novel_dir, args.chapter, args.proposal_id, approve=args.approve)
    else:
        if not args.snapshot_id:
            parser.error("restore 必须提供 --snapshot-id")
        result = restore_snapshot(novel_dir, args.chapter, args.snapshot_id)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
