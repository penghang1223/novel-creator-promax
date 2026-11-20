#!/usr/bin/env python3
"""Cross-check novel artifacts: chapters, passports, commits and novel_state.

Exit codes:
    0  没有 error（--strict 下也没有 warning）
    1  存在 error（或 --strict 下存在 warning）
    2  参数或运行错误
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from novel_creation_promax.core.integrity import (  # noqa: E402
    report_has_errors,
    verify_novel_integrity,
    verify_root_integrity,
)

SEVERITY_LABELS = {"error": "错误", "warning": "警告", "info": "提示"}


def _render_novel_text(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        f"项目: {report['title']} ({report['platform']})",
        f"检查章节: {summary['chapters_checked']} | 错误: {summary['errors']} | 警告: {summary['warnings']}",
    ]
    findings = report["findings"]
    if not findings:
        lines.append("结果: 未发现一致性问题")
        return "\n".join(lines)

    ordered = sorted(
        findings,
        key=lambda item: ({"error": 0, "warning": 1, "info": 2}.get(item["severity"], 9), item.get("chapter", 0)),
    )
    lines.append("")
    for index, finding in enumerate(ordered, start=1):
        chapter = f" 第{finding['chapter']}章" if finding.get("chapter") is not None else ""
        label = SEVERITY_LABELS.get(finding["severity"], finding["severity"])
        lines.append(f"{index}. [{label}] {finding['code']}{chapter}: {finding['message']}")
        if finding.get("path"):
            lines.append(f"   路径: {finding['path']}")
        if finding.get("hint"):
            lines.append(f"   建议: {finding['hint']}")
    return "\n".join(lines)


def _render_root_text(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        f"输出根目录: {report['root']}",
        f"项目: {summary['projects']} | 检查章节: {summary['chapters_checked']} | 错误: {summary['errors']} | 警告: {summary['warnings']}",
    ]
    for project in report["projects"]:
        project_summary = project["summary"]
        mark = "ERROR" if project_summary["errors"] else ("WARN" if project_summary["warnings"] else "OK")
        lines.append(
            f"- [{mark}] {project['title']} ({project['platform']}): "
            f"{project_summary['chapters_checked']} 章, "
            f"错误 {project_summary['errors']}, 警告 {project_summary['warnings']}"
        )
        for finding in project["findings"]:
            if finding["severity"] == "error":
                chapter = f" 第{finding['chapter']}章" if finding.get("chapter") is not None else ""
                lines.append(f"    {finding['code']}{chapter}: {finding['message']}")
    return "\n".join(lines)


def _strict_failed(report: dict[str, Any]) -> bool:
    return report_has_errors(report)


def main() -> int:
    parser = argparse.ArgumentParser(description="校验章节、passport、commit 与 novel_state 的一致性")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--novel-dir", help="单本小说目录")
    target.add_argument("--root", default="", help="novel_output 根目录，扫描全部项目")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    parser.add_argument("--strict", action="store_true", help="warning 也视为失败")
    args = parser.parse_args()

    try:
        if args.novel_dir:
            report = verify_novel_integrity(Path(args.novel_dir).expanduser().resolve())
        else:
            report = verify_root_integrity(Path(args.root).expanduser().resolve())
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(_render_novel_text(report) if args.novel_dir else _render_root_text(report))

    failed = _strict_failed(report)
    if args.strict:
        summary = report["summary"]
        failed = failed or summary["warnings"] > 0
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
