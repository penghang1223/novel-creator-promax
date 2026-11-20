#!/usr/bin/env python3
"""Generate per-book and workspace-wide markdown dashboards."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from novel_creation_promax.core.dashboard import (  # noqa: E402
    check_dashboards,
    global_dashboard_path,
    write_dashboards,
)
from novel_creation_promax.core.roots import workspace_root  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="生成总看板与单书看板")
    parser.add_argument("--workspace", default="", help="工作区根目录")
    parser.add_argument("--novel-dir", default="", help="只刷新某一本书")
    parser.add_argument("--check", action="store_true", help="只检查看板是否漂移")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve() if args.workspace else workspace_root()
    novel_dir = Path(args.novel_dir).expanduser().resolve() if args.novel_dir else None

    if args.check:
        problems = check_dashboards(workspace, novel_dir)
        if args.json:
            print(json.dumps(
                {"workspace": str(workspace), "problems": problems, "passed": not problems},
                ensure_ascii=False,
                indent=2,
            ))
        else:
            print("看板检查: " + ("PASS" if not problems else f"FAIL ({len(problems)})"))
            for item in problems:
                print(f"  - {item}")
        return 0 if not problems else 1

    paths = write_dashboards(workspace, novel_dir)
    if args.json:
        print(json.dumps(
            {"workspace": str(workspace), "written": [str(path) for path in paths]},
            ensure_ascii=False,
            indent=2,
        ))
    else:
        print("已生成看板:")
        for path in paths:
            print(f"  - {path}")
        print(f"总看板: {global_dashboard_path(workspace)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
