#!/usr/bin/env python3
"""Audit the generated novel_output tree without changing files."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from novel_creation_promax.core.paths import (  # noqa: E402
    CHAPTER_EXTENSIONS,
    infer_chapter_number,
    normalize_title,
    split_project_folder_name,
)

IGNORED_OUTPUT_DIRS = {
    "素材",
    "archive",
    "covers",
    "uploaded",
    "short_uploaded",
    "_workspace",
}

BODY_ARTIFACT_RE = re.compile(
    r"(?:virtual_reader|readability|character_profiles|metaphor|full_review|"
    r"coherence|emotion_curve|plot_hole|hook|pacing|project_bootstrap|"
    r"_ai_report)(?:$|[_.-])",
    re.IGNORECASE,
)
STATE_BACKUP_RE = re.compile(r"^novel_state\.json\.bak-")


def issue(code: str, severity: str, path: Path, detail: str) -> dict[str, str]:
    return {
        "code": code,
        "severity": severity,
        "path": path.as_posix(),
        "detail": detail,
    }


def project_dirs(output_root: Path) -> list[Path]:
    if not output_root.is_dir():
        return []
    return sorted(
        project
        for platform in output_root.iterdir()
        if platform.is_dir() and platform.name not in IGNORED_OUTPUT_DIRS
        for project in platform.iterdir()
        if project.is_dir() and project.name not in IGNORED_OUTPUT_DIRS
    )


def body_artifacts(project: Path) -> list[Path]:
    body = project / "正文"
    if not body.is_dir():
        return []
    found: list[Path] = []
    for path in sorted(body.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() in CHAPTER_EXTENSIONS and infer_chapter_number(path) is not None:
            continue
        if BODY_ARTIFACT_RE.search(path.stem):
            found.append(path)
    return found


def audit(output_root: Path) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    projects = project_dirs(output_root)
    collisions: defaultdict[tuple[str, str], list[Path]] = defaultdict(list)

    if (output_root / "素材").is_dir():
        issues.append(
            issue(
                "workspace-mixed-with-output",
                "warning",
                output_root / "素材",
                "顶层素材是工作区内容，不是平台项目；建议后续迁移到 novel_output/_workspace/ 或 knowledge_base/15_Ideas/。",
            )
        )

    for project in projects:
        platform = project.parent.name
        _, title = split_project_folder_name(project.name)
        collisions[(platform, normalize_title(title))].append(project)

        for path in body_artifacts(project):
            issues.append(
                issue(
                    "body-artifact-mixed",
                    "warning",
                    path,
                    "正文目录含审计报告或项目元数据，应归入 素材/reports/ 或 记忆/。",
                )
            )

        for path in project.iterdir():
            if path.is_file() and STATE_BACKUP_RE.match(path.name):
                issues.append(
                    issue(
                        "state-backup-scattered",
                        "warning",
                        path,
                        "novel_state 备份散落在项目根目录，应归入 素材/state_backups/。",
                    )
                )

    for (platform, title), paths in sorted(collisions.items()):
        if title and len(paths) > 1:
            issues.append(
                issue(
                    "duplicate-project-title",
                    "error",
                    output_root / platform,
                    f"同一平台存在同名项目目录：{', '.join(path.name for path in paths)}。",
                )
            )

    summary = {
        "projects": len(projects),
        "issues": len(issues),
        "errors": sum(item["severity"] == "error" for item in issues),
        "warnings": sum(item["severity"] == "warning" for item in issues),
        "body_artifacts": sum(item["code"] == "body-artifact-mixed" for item in issues),
        "state_backups": sum(item["code"] == "state-backup-scattered" for item in issues),
        "duplicate_titles": sum(item["code"] == "duplicate-project-title" for item in issues),
    }
    return {"root": str(output_root), "summary": summary, "issues": issues}


def main() -> int:
    parser = argparse.ArgumentParser(description="审计 novel_output 目录架构（只读）")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--strict", action="store_true", help="发现错误时返回非零")
    args = parser.parse_args()

    result = audit(PROJECT_ROOT / "novel_output")
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        summary = result["summary"]
        print(
            f"projects={summary['projects']} issues={summary['issues']} "
            f"errors={summary['errors']} warnings={summary['warnings']}"
        )
        for item in result["issues"]:
            print(f"[{item['severity']}] {item['code']}: {item['path']} — {item['detail']}")
    return 1 if args.strict and result["summary"]["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
