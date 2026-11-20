#!/usr/bin/env python3
"""Manage optional scene-level passports for one chapter."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from novel_creation_promax.core.jsonio import load_json  # noqa: E402
from novel_creation_promax.core.scene_passport import (  # noqa: E402
    initialize_scene_plan,
    list_scene_passports,
    sync_chapter_scene_index,
    transition_scene,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="管理章节场景 passport")
    parser.add_argument("command", choices=["init", "list", "update"])
    parser.add_argument("--novel-dir", required=True)
    parser.add_argument("--chapter", type=int, required=True)
    parser.add_argument("--scene", type=int, default=0)
    parser.add_argument("--status", choices=["planning", "draft", "audit", "pass", "blocked"], default="")
    parser.add_argument("--plan-file", default="")
    parser.add_argument("--error", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    novel_dir = Path(args.novel_dir).resolve()
    if args.command == "init":
        if not args.plan_file:
            parser.error("init 必须提供 --plan-file")
        payload = load_json(Path(args.plan_file).resolve(), {})
        plan = payload.get("scenes") if isinstance(payload, dict) else payload
        if not isinstance(plan, list):
            parser.error("plan 文件必须是场景数组或 {\"scenes\": [...]} 对象")
        result = initialize_scene_plan(novel_dir, args.chapter, plan)
    elif args.command == "list":
        result = {"scenes": list_scene_passports(novel_dir, args.chapter), "summary": sync_chapter_scene_index(novel_dir, args.chapter)}
    else:
        if not args.scene or not args.status:
            parser.error("update 必须提供 --scene 和 --status")
        result = transition_scene(novel_dir, args.chapter, args.scene, args.status, error=args.error)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
