#!/usr/bin/env python3
"""Backfill missing project charter and risk register files safely."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from novel_creation_promax.core.jsonio import load_json  # noqa: E402
from novel_creation_promax.core.paths import split_project_folder_name  # noqa: E402
from novel_creation_promax.core.project_management import (  # noqa: E402
    render_project_charter,
    render_risk_register,
)

IGNORED_PLATFORMS = {"素材", "_workspace", "covers", "archive", "uploaded", "short_uploaded"}


def project_info(novel_dir: Path) -> tuple[str, str, str]:
    state = load_json(novel_dir / "novel_state.json", {})
    title = state.get("title") if isinstance(state, dict) else ""
    _, fallback = split_project_folder_name(novel_dir.name)
    return str(title or fallback or novel_dir.name), novel_dir.parent.name, str(
        state.get("genre", "待填写") if isinstance(state, dict) else "待填写"
    )


def backfill(novel_dir: Path, *, apply: bool = False) -> dict[str, object]:
    title, platform, genre = project_info(novel_dir)
    files = {
        "项目章程.md": render_project_charter(title, platform, genre, "待填写"),
        "风险登记表.md": render_risk_register(title),
    }
    actions = []
    for name, content in files.items():
        path = novel_dir / name
        if path.exists():
            actions.append({"file": name, "action": "exists"})
        elif apply:
            path.write_text(content, encoding="utf-8")
            actions.append({"file": name, "action": "created"})
        else:
            actions.append({"file": name, "action": "create"})
    return {"novel_dir": str(novel_dir), "actions": actions, "applied": apply}


def discover_all() -> list[Path]:
    output = PROJECT_ROOT / "novel_output"
    return sorted(
        novel_dir
        for platform_dir in output.iterdir()
        if platform_dir.is_dir() and platform_dir.name not in IGNORED_PLATFORMS
        for novel_dir in platform_dir.iterdir()
        if novel_dir.is_dir() and novel_dir.name not in {"素材", "covers", "archive", "uploaded", "short_uploaded"}
    ) if output.exists() else []


def main() -> int:
    parser = argparse.ArgumentParser(description="补齐项目章程.md 与风险登记表.md")
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--novel-dir")
    scope.add_argument("--all", action="store_true")
    parser.add_argument("--apply", action="store_true", help="实际创建缺失文件")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.novel_dir:
        raw = Path(args.novel_dir)
        targets = [raw if raw.is_absolute() else PROJECT_ROOT / raw]
    else:
        targets = discover_all()
    results = [backfill(path, apply=args.apply) for path in targets]
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for result in results:
            actions = ", ".join(f"{item['file']}={item['action']}" for item in result["actions"])
            print(f"{result['novel_dir']}: {actions}")
        if not args.apply:
            print("[dry-run] 未创建文件；加 --apply 才会写入缺失管理文件。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
