#!/usr/bin/env python3
"""Normalize safe, mechanically identifiable novel_output artifacts.

Default mode is dry-run. ``--apply`` moves files without overwriting existing
targets. Duplicate projects require the explicit ``--archive-duplicates`` flag.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from novel_creation_promax.core.paths import CHAPTER_EXTENSIONS, infer_chapter_number, normalize_title, split_project_folder_name  # noqa: E402

IGNORED_OUTPUT_DIRS = {"素材", "archive", "covers", "uploaded", "short_uploaded", "_workspace"}
BODY_ARTIFACT_RE = re.compile(
    r"(?:virtual_reader|readability|character_profiles|metaphor|full_review|"
    r"coherence|emotion_curve|plot_hole|hook|pacing|project_bootstrap|"
    r"_ai_report)(?:$|[_.-])",
    re.IGNORECASE,
)
STATE_BACKUP_RE = re.compile(r"^novel_state\.json\.bak-")
MEMORY_ARCHIVE_RE = re.compile(r"^memory\.merged-")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def action(source: Path, target: Path, *, apply: bool) -> dict[str, str]:
    result = {"source": source.as_posix(), "target": target.as_posix(), "status": "planned"}
    if target.exists():
        if target.is_file() and digest(source) == digest(target):
            result["status"] = "duplicate-target"
        else:
            result["status"] = "conflict"
        return result
    if apply:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
        result["status"] = "moved"
    return result


def body_artifact_moves(project: Path, *, apply: bool) -> list[dict[str, str]]:
    body = project / "正文"
    if not body.is_dir():
        return []
    actions: list[dict[str, str]] = []
    for source in sorted(body.rglob("*")):
        if not source.is_file():
            continue
        if source.suffix.lower() in CHAPTER_EXTENSIONS and infer_chapter_number(source) is not None:
            continue
        if not BODY_ARTIFACT_RE.search(source.stem):
            continue
        relative = source.relative_to(body)
        if source.name == "project_bootstrap.json":
            target = project / "记忆" / source.name
        else:
            target = project / "素材" / "reports" / relative
        actions.append(action(source, target, apply=apply))
    return actions


def state_backup_moves(project: Path, *, apply: bool) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    for source in sorted(project.iterdir()):
        if source.is_file() and STATE_BACKUP_RE.match(source.name):
            actions.append(action(source, project / "素材" / "state_backups" / source.name, apply=apply))
    return actions


def memory_archive_moves(project: Path, *, apply: bool) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    for source in sorted(project.iterdir()):
        if source.is_dir() and MEMORY_ARCHIVE_RE.match(source.name):
            actions.append(action(source, project / "记忆" / "_archive" / source.name, apply=apply))
    return actions


def duplicate_project_moves(output_root: Path, *, apply: bool) -> list[dict[str, str]]:
    groups: dict[tuple[str, str], list[Path]] = {}
    for platform in sorted(output_root.iterdir()):
        if not platform.is_dir() or platform.name in IGNORED_OUTPUT_DIRS:
            continue
        for project in sorted(platform.iterdir()):
            if not project.is_dir() or project.name in IGNORED_OUTPUT_DIRS:
                continue
            _, title = split_project_folder_name(project.name)
            groups.setdefault((platform.name, normalize_title(title)), []).append(project)

    actions: list[dict[str, str]] = []
    archive_root = output_root / "archive"
    for (platform_name, _), projects in sorted(groups.items()):
        numbered = [path for path in projects if split_project_folder_name(path.name)[0]]
        unnumbered = [path for path in projects if not split_project_folder_name(path.name)[0]]
        if len(numbered) != 1 or not unnumbered:
            continue
        for source in unnumbered:
            target = archive_root / platform_name / source.name
            actions.append(action(source, target, apply=apply))
    return actions


def main() -> int:
    parser = argparse.ArgumentParser(description="整理 novel_output 中明确可识别的历史产物")
    parser.add_argument("--apply", action="store_true", help="实际移动文件")
    parser.add_argument("--archive-duplicates", action="store_true", help="将同平台无编号重复项目移到 novel_output/archive/")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    output_root = PROJECT_ROOT / "novel_output"
    results: list[dict[str, Any]] = []
    for platform in sorted(output_root.iterdir()):
        if not platform.is_dir() or platform.name in IGNORED_OUTPUT_DIRS:
            continue
        for project in sorted(platform.iterdir()):
            if not project.is_dir() or project.name in IGNORED_OUTPUT_DIRS:
                continue
            for item in body_artifact_moves(project, apply=args.apply):
                results.append({"kind": "body-artifact", **item})
            for item in state_backup_moves(project, apply=args.apply):
                results.append({"kind": "state-backup", **item})
            for item in memory_archive_moves(project, apply=args.apply):
                results.append({"kind": "memory-archive", **item})
    if args.archive_duplicates:
        for item in duplicate_project_moves(output_root, apply=args.apply):
            results.append({"kind": "duplicate-project", **item})

    summary = {
        "planned": sum(item["status"] == "planned" for item in results),
        "moved": sum(item["status"] == "moved" for item in results),
        "duplicate_target": sum(item["status"] == "duplicate-target" for item in results),
        "conflict": sum(item["status"] == "conflict" for item in results),
    }
    payload = {"apply": args.apply, "summary": summary, "actions": results}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(
            f"planned={summary['planned']} moved={summary['moved']} "
            f"duplicate_target={summary['duplicate_target']} conflict={summary['conflict']}"
        )
        for item in results:
            print(f"[{item['status']}] {item['source']} -> {item['target']}")
        if not args.apply:
            print("[dry-run] 未移动文件；加 --apply 才会实际执行。")
    return 1 if summary["conflict"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
