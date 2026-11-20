#!/usr/bin/env python3
"""Audit knowledge_base structure, lifecycle boundaries, and project contracts."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_ROOT = PROJECT_ROOT / "knowledge_base"
STRUCTURE_PATH = KNOWLEDGE_ROOT / "_STRUCTURE.json"


def load_structure() -> dict:
    return json.loads(STRUCTURE_PATH.read_text(encoding="utf-8"))


def audit() -> dict:
    structure = load_structure()
    files = [
        path for path in KNOWLEDGE_ROOT.rglob("*")
        if path.is_file() and ".obsidian" not in path.parts
    ]
    top_counts = Counter(path.relative_to(KNOWLEDGE_ROOT).parts[0] for path in files)
    errors: list[str] = []
    warnings: list[str] = []

    required_root_files = {
        "00_Index.md",
        "README.md",
        "CLAUDE.md",
        "_ROUTES.json",
        "_ROUTING.md",
        "_LEGACY_INDEX.md",
        "_STRUCTURE.json",
    }
    for name in sorted(required_root_files):
        if not (KNOWLEDGE_ROOT / name).is_file():
            errors.append(f"缺少知识库根文件: {name}")

    for domain in structure.get("domains", []):
        path = KNOWLEDGE_ROOT / domain["path"]
        if not path.is_dir():
            errors.append(f"缺少知识库域目录: {domain['path']}")

    inbox = KNOWLEDGE_ROOT / "00_Inbox"
    inbox_files = [
        path for path in inbox.rglob("*")
        if path.is_file() and path.name not in {"README.md"}
    ] if inbox.is_dir() else []
    if inbox_files:
        warnings.append(f"00_Inbox 仍有 {len(inbox_files)} 个待归类文件/目录")

    # 归档域由 _STRUCTURE.json 声明才要求存在：运行精简库可能不含 90_Archive。
    declares_archive = any(
        str(item.get("path", "")).startswith("90_Archive")
        for item in structure.get("domains", [])
    )
    archive_root = KNOWLEDGE_ROOT / "90_Archive"
    if declares_archive and not archive_root.is_dir():
        errors.append("缺少历史归档域: 90_Archive")
    for archived in structure.get("archive_subtrees", []):
        path = KNOWLEDGE_ROOT / archived["path"]
        if not path.is_dir():
            errors.append(f"归档卷缺失: {archived['path']}")

    project_contract = next(
        (item for item in structure.get("domains", []) if item.get("path") == "80_Projects"),
        {},
    )
    project_overrides = {
        item.get("path"): item
        for item in structure.get("project_overrides", [])
        if isinstance(item, dict) and item.get("path")
    }
    projects_root = KNOWLEDGE_ROOT / "80_Projects"
    incomplete_projects = []
    if projects_root.is_dir():
        for project in sorted(path for path in projects_root.iterdir() if path.is_dir()):
            relative_project = project.relative_to(KNOWLEDGE_ROOT).as_posix()
            override = project_overrides.get(relative_project, {})
            if override.get("contract") == "minimal":
                continue
            missing_files = [
                name for name in project_contract.get("required_files", [])
                if not (project / name).is_file()
            ]
            missing_dirs = [
                name for name in project_contract.get("required_dirs", [])
                if not (project / name).is_dir()
            ]
            if missing_files or missing_dirs:
                incomplete_projects.append({
                    "path": project.relative_to(PROJECT_ROOT).as_posix(),
                    "missing_files": missing_files,
                    "missing_dirs": missing_dirs,
                })
    if incomplete_projects:
        warnings.append(f"{len(incomplete_projects)} 个项目目录未满足 80_Projects 契约")

    index_text = (KNOWLEDGE_ROOT / "00_Index.md").read_text(encoding="utf-8")
    reported_total = re.search(r"总文件数\*\*：([0-9]+)", index_text)
    if reported_total and int(reported_total.group(1)) != len(files):
        warnings.append(
            f"00_Index.md 总文件数已过期: {reported_total.group(1)} -> {len(files)}"
        )

    return {
        "root": str(KNOWLEDGE_ROOT),
        "file_count": len(files),
        "top_counts": dict(sorted(top_counts.items())),
        "inbox_count": len(inbox_files),
        "incomplete_projects": incomplete_projects,
        "errors": errors,
        "warnings": warnings,
        "passed": not errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="审查 knowledge_base 目录契约与生命周期边界")
    parser.add_argument("--json", action="store_true", help="输出 JSON 报告")
    args = parser.parse_args()
    report = audit()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("知识库目录架构审计")
        print(f"files={report['file_count']}")
        print("top-level=" + ", ".join(f"{key}:{value}" for key, value in report["top_counts"].items()))
        for message in report["errors"]:
            print(f"  [FAIL] {message}")
        for message in report["warnings"]:
            print(f"  [WARN] {message}")
        if not report["errors"] and not report["warnings"]:
            print("  [OK] 结构契约通过")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
