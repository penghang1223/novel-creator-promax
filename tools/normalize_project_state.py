#!/usr/bin/env python3
"""Preview or apply the canonical novel_state.json migration.

Examples:
    python tools/normalize_project_state.py --novel-dir "novel_output/番茄/001_示例"
    python tools/normalize_project_state.py --all --apply
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from novel_creation_promax.core.project_state import migrate_state_file  # noqa: E402


def discover_all() -> list[Path]:
    return sorted(path.parent for path in (PROJECT_ROOT / "novel_output").glob("*/*/novel_state.json"))


def main() -> int:
    parser = argparse.ArgumentParser(description="规范化 novel_state.json（默认 dry-run）")
    parser.add_argument("--novel-dir", default="", help="单个小说目录")
    parser.add_argument("--all", action="store_true", help="扫描 novel_output 下全部项目")
    parser.add_argument("--apply", action="store_true", help="实际写回并生成备份")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    if bool(args.novel_dir) == bool(args.all):
        parser.error("需要且只能指定 --novel-dir 或 --all")

    if args.novel_dir:
        raw = Path(args.novel_dir)
        targets = [raw if raw.is_absolute() else PROJECT_ROOT / raw]
    else:
        targets = discover_all()

    results = [migrate_state_file(path, apply=args.apply) for path in targets]
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0

    for result in results:
        if "error" in result:
            print(f"[error] {result['novel_dir']}: {result['error']}")
            continue
        action = "applied" if result["applied"] else "dry-run"
        print(f"[{action}] {result['novel_dir']}: {', '.join(result['changed_keys']) or '无需修改'}")
    if not args.apply:
        print("\n[dry-run] 未写回；加 --apply 后生效，并自动备份原文件。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
