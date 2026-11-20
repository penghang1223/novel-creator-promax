#!/usr/bin/env python3
"""Safely converge duplicated ``memory`` and ``记忆`` directories.

The default mode is a dry-run. ``--apply`` copies only files missing from the
preferred directory; conflicting files and source files are never overwritten
or deleted automatically.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

IGNORED_PLATFORMS = {"素材", "_workspace", "covers", "archive", "uploaded", "short_uploaded"}


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def compare_files(source: Path, target: Path) -> str:
    if not target.exists():
        return "missing_target"
    if digest(source) == digest(target):
        return "duplicate"
    if source.suffix.lower() == ".json":
        try:
            source_json: Any = json.loads(source.read_text(encoding="utf-8-sig"))
            target_json: Any = json.loads(target.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return "conflict"
        if source_json == target_json:
            return "duplicate"
    return "conflict"


def merge_json_values(target: Any, source: Any, path: str = "") -> tuple[Any, list[str]]:
    """Merge source data without replacing non-empty target values."""
    if isinstance(target, dict) and isinstance(source, dict):
        merged = copy.deepcopy(target)
        conflicts: list[str] = []
        for key, source_value in source.items():
            key_path = f"{path}.{key}" if path else key
            if key not in merged:
                merged[key] = copy.deepcopy(source_value)
                continue
            merged[key], nested = merge_json_values(merged[key], source_value, key_path)
            conflicts.extend(nested)
        return merged, conflicts
    if isinstance(target, list) and isinstance(source, list):
        if not target:
            return copy.deepcopy(source), []
        merged = copy.deepcopy(target)
        seen = {json.dumps(item, ensure_ascii=False, sort_keys=True) for item in merged}
        for item in source:
            marker = json.dumps(item, ensure_ascii=False, sort_keys=True)
            if marker not in seen:
                merged.append(copy.deepcopy(item))
                seen.add(marker)
        return merged, []
    if target == source:
        return copy.deepcopy(target), []
    if path.endswith("updated_at"):
        return max(str(target), str(source)), []
    if path.endswith("created_at"):
        return min(str(target), str(source)), []
    return copy.deepcopy(target), [path or "<root>"]


def merge_one(
    novel_dir: Path,
    preferred: str,
    *,
    apply: bool = False,
    merge_json: bool = False,
    archive_source: bool = False,
) -> dict[str, Any]:
    target = novel_dir / preferred
    source_name = "memory" if preferred == "记忆" else "记忆"
    source = novel_dir / source_name
    if not source.is_dir() or not target.is_dir():
        return {"novel_dir": str(novel_dir), "status": "not_applicable"}

    actions: list[dict[str, str]] = []
    unresolved: list[str] = []
    for source_file in sorted(path for path in source.rglob("*") if path.is_file()):
        relative = source_file.relative_to(source)
        target_file = target / relative
        status = compare_files(source_file, target_file)
        action = "copy" if status == "missing_target" else "keep_source"
        if status == "conflict" and merge_json and source_file.suffix.lower() == ".json":
            try:
                source_json = json.loads(source_file.read_text(encoding="utf-8-sig"))
                target_json = json.loads(target_file.read_text(encoding="utf-8-sig"))
                merged, conflicts = merge_json_values(target_json, source_json)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                conflicts = [relative.as_posix()]
            if not conflicts:
                status = "merged_json"
                action = "merge"
                if apply:
                    target_file.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            else:
                unresolved.extend(f"{relative.as_posix()}:{item}" for item in conflicts)
        if apply and status == "missing_target":
            target_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, target_file)
            action = "copied"
        actions.append({"file": relative.as_posix(), "status": status, "action": action})

    archived_source = ""
    if apply and archive_source and not unresolved:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        archived = novel_dir / f"{source_name}.merged-{stamp}"
        source.rename(archived)
        archived_source = str(archived)

    return {
        "novel_dir": str(novel_dir),
        "target": preferred,
        "source": source_name,
        "applied": apply,
        "archived_source": archived_source,
        "unresolved": unresolved,
        "actions": actions,
        "summary": {
            "missing_target": sum(item["status"] == "missing_target" for item in actions),
            "duplicate": sum(item["status"] == "duplicate" for item in actions),
            "conflict": sum(item["status"] == "conflict" for item in actions),
            "merged_json": sum(item["status"] == "merged_json" for item in actions),
        },
    }


def discover_all() -> list[Path]:
    output = PROJECT_ROOT / "novel_output"
    return sorted(
        novel_dir
        for platform_dir in output.iterdir()
        if platform_dir.is_dir() and platform_dir.name not in IGNORED_PLATFORMS
        for novel_dir in platform_dir.iterdir()
        if novel_dir.is_dir() and (novel_dir / "memory").is_dir() and (novel_dir / "记忆").is_dir()
    ) if output.exists() else []


def main() -> int:
    parser = argparse.ArgumentParser(description="无损合并 memory 与 记忆 目录")
    parser.add_argument("--novel-dir", default="", help="单个小说目录")
    parser.add_argument("--all", action="store_true", help="扫描全部重复目录")
    parser.add_argument("--prefer", choices=["记忆", "memory"], default="记忆", help="保留为主目录的别名")
    parser.add_argument("--apply", action="store_true", help="复制目标缺失文件；不覆盖冲突、不删除源文件")
    parser.add_argument("--merge-json", action="store_true", help="对 JSON 冲突执行非破坏性字段/列表合并")
    parser.add_argument("--archive-source", action="store_true", help="应用且无冲突后，将源目录改名归档")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    if bool(args.novel_dir) == bool(args.all):
        parser.error("需要且只能指定 --novel-dir 或 --all")
    if args.novel_dir:
        raw = Path(args.novel_dir)
        targets = [raw if raw.is_absolute() else PROJECT_ROOT / raw]
    else:
        targets = discover_all()

    if args.archive_source and not args.apply:
        parser.error("--archive-source 需要同时指定 --apply")
    results = [
        merge_one(
            path,
            args.prefer,
            apply=args.apply,
            merge_json=args.merge_json,
            archive_source=args.archive_source,
        )
        for path in targets
    ]
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for result in results:
            summary = result.get("summary", {})
            print(
                f"[{result['novel_dir']}] missing={summary.get('missing_target', 0)} "
                f"duplicate={summary.get('duplicate', 0)} conflict={summary.get('conflict', 0)}"
                f" merged={summary.get('merged_json', 0)}"
            )
        if not args.apply:
            print("[dry-run] 未复制文件；加 --apply 才会把源目录独有文件复制到主目录。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
