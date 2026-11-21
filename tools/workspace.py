#!/usr/bin/env python3
"""Confirm where novel products are allowed to be written.

The marker lives in the workspace (``.novel-workspace.json``), so it follows
the folder but invalidates when the folder is moved. This CLI is the only
place that writes the marker; pipeline entry points only read it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from novel_creation_promax.core import workspace_confirmation as wc  # noqa: E402
from novel_creation_promax.core.roots import workspace_root  # noqa: E402


def _resolve(value: str) -> Path:
    return Path(value).expanduser().resolve() if value else workspace_root().resolve()


def _print_human(payload: dict) -> None:
    print(f"工作区: {payload['workspace']}")
    print(f"已确认: {'是' if payload['confirmed'] else '否'}")
    print(f"原因: {payload['reason']}")
    print(f"存量书: {payload['legacy_books']}")
    print(f"标记: {payload['marker']}")
    if payload["dangerous"]:
        print(f"危险根: {payload['dangerous']}")
    if payload.get("auto_confirmed"):
        print("动作: 已为存量工作区补写确认标记")
    if not payload["confirmed"]:
        if payload["dangerous"] in ("plugin_root", "root"):
            print(wc.refusal_message(payload))
            return
        print("将创建/写入:")
        for item in payload["write_paths"]:
            print(f"  - {item}")
        print("确认: python3 tools/workspace.py confirm")


def main() -> int:
    parser = argparse.ArgumentParser(description="工作区输出位置确认")
    parser.add_argument("--workspace", default="", help="工作区根目录，默认读取 CLAUDE_PROJECT_DIR")
    sub = parser.add_subparsers(dest="command", required=True)

    status_parser = sub.add_parser("status", help="查看确认状态")
    status_parser.add_argument("--json", action="store_true")

    confirm_parser = sub.add_parser("confirm", help="确认当前工作区")
    confirm_parser.add_argument("--legacy", action="store_true", help="标记为存量工作区自动确认")
    confirm_parser.add_argument("--json", action="store_true")

    forget_parser = sub.add_parser("forget", help="删除确认标记")
    forget_parser.add_argument("--json", action="store_true")

    args = parser.parse_args()
    workspace = _resolve(args.workspace)

    if args.command == "status":
        payload = wc.status(workspace)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            _print_human(payload)
        return 0

    if args.command == "confirm":
        try:
            payload = wc.confirm(workspace, by="legacy" if args.legacy else "user")
        except wc.WorkspaceConfirmationError as exc:
            if args.json:
                print(json.dumps(exc.status, ensure_ascii=False, indent=2))
            else:
                print(str(exc), file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"已确认工作区: {payload['workspace']}")
            print(f"标记: {payload['marker']}")
        return 0

    if args.command == "forget":
        removed = wc.forget(workspace)
        payload = {"workspace": str(workspace), "removed": removed}
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print("已删除确认标记" if removed else "确认标记不存在")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
