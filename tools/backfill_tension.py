#!/usr/bin/env python3
"""Safely estimate historical chapter tension reports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from novel_creation_promax.core.paths import list_chapter_files  # noqa: E402
from novel_creation_promax.core.story_index import iter_output_projects  # noqa: E402
from novel_creation_promax.core.tension_curve import estimate_chapter_tension  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="为历史章节生成可追溯的启发式张力报告")
    parser.add_argument("--root", default=str(PROJECT_ROOT))
    parser.add_argument("--novel-dir", default="")
    parser.add_argument("--chapter", type=int, default=0)
    parser.add_argument("--apply", action="store_true", help="实际写入素材/tension；默认只预览")
    parser.add_argument("--force", action="store_true", help="覆盖已有张力报告")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    novels = [Path(args.novel_dir).resolve()] if args.novel_dir else list(iter_output_projects(root / "novel_output"))
    reports = []
    for novel_dir in novels:
        chapters = [(args.chapter, None)] if args.chapter else list_chapter_files(novel_dir)
        for chapter, _chapter_file in chapters:
            report = estimate_chapter_tension(novel_dir, chapter, save=args.apply, force=args.force)
            report["novel_dir"] = str(novel_dir)
            report["applied"] = bool(args.apply and report.get("status") in {"estimated", "unavailable"})
            reports.append(report)
    result = {"apply": args.apply, "force": args.force, "count": len(reports), "reports": reports}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"处理 {len(reports)} 章，写入={'是' if args.apply else '否'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
