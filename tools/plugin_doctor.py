#!/usr/bin/env python3
"""Read-only health check for the plugin installation and user workspace."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from novel_creation_promax.core.roots import plugin_root, workspace_root  # noqa: E402

REQUIRED_PLUGIN_FILES = (
    ".claude-plugin/plugin.json",
    "skills/novel-creator/SKILL.md",
    "commands/write.md",
    "hooks/hooks.json",
    "novel_creation_promax/SKILL.md",
    "novel_creation_promax/MODE_REGISTRY.md",
    "novel_creation_promax/scripts/write_pipeline.py",
    "knowledge_base/_ROUTES.json",
    "knowledge_base/_ROUTING.md",
    "tools/verify_project_integrity.py",
    "tools/workflow.py",
    "docs/WORKFLOW.md",
)

OPTIONAL_DEPS = (
    ("PIL", "Pillow", "封面生成"),
    ("jieba", "jieba", "风格 DNA / 人物一致性"),
    ("requests", "requests", "知识摄入 / 飞书文档"),
    ("fastapi", "FastAPI", "Web Dashboard"),
    ("playwright", "Playwright", "自动发布"),
)


def _frontmatter_problem(path: Path, *, require_name: bool = True) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return f"无法读取: {exc}"
    if not text.startswith("---"):
        return "缺少 frontmatter"
    parts = text.split("---", 2)
    if len(parts) < 3:
        return "frontmatter 未闭合"
    block = parts[1]
    fields = ("name", "description") if require_name else ("description",)
    for field in fields:
        if f"{field}:" not in block:
            return f"frontmatter 缺少 {field}"
    return ""


def inspect(workspace: Path | None = None) -> dict[str, Any]:
    plugin = plugin_root()
    workspace = (workspace or workspace_root()).resolve()
    checks: list[dict[str, Any]] = []

    def add(name: str, status: str, detail: str) -> None:
        checks.append({"name": name, "status": status, "detail": detail})

    for relative in REQUIRED_PLUGIN_FILES:
        path = plugin / relative
        add(f"plugin:{relative}", "pass" if path.is_file() else "fail", "存在" if path.is_file() else "缺失")

    for skill in sorted((plugin / "skills").glob("*/SKILL.md")):
        problem = _frontmatter_problem(skill)
        add(f"skill:{skill.parent.name}", "pass" if not problem else "fail", problem or "frontmatter ok")

    for command in sorted((plugin / "commands").glob("*.md")):
        problem = _frontmatter_problem(command, require_name=False)
        add(f"command:{command.stem}", "pass" if not problem else "fail", problem or "frontmatter ok")

    if sys.version_info < (3, 10):
        add("python", "warn", f"{sys.version.split()[0]}，建议 3.10+")
    else:
        add("python", "pass", sys.version.split()[0])

    for module, label, purpose in OPTIONAL_DEPS:
        found = importlib.util.find_spec(module) is not None
        add(
            f"dependency:{label}",
            "pass" if found else "warn",
            "已安装" if found else f"未安装（仅影响{purpose}）",
        )

    if workspace.is_dir():
        add("workspace", "pass", str(workspace))
    else:
        add("workspace", "fail", f"不存在: {workspace}")

    output = workspace / "novel_output"
    books = [
        path
        for path in sorted(output.glob("*/*/novel_state.json"))
        if path.is_file()
    ] if output.is_dir() else []
    add("workspace:novel_output", "pass" if output.is_dir() else "warn", f"发现 {len(books)} 本书")

    for relative in ("MEMORY.md", ".claude/memory"):
        path = workspace / relative
        add(f"workspace:{relative}", "pass" if path.exists() else "warn", "存在" if path.exists() else "未发现")

    errors = sum(1 for item in checks if item["status"] == "fail")
    warnings = sum(1 for item in checks if item["status"] == "warn")
    return {
        "plugin_root": str(plugin),
        "workspace_root": str(workspace),
        "summary": {"errors": errors, "warnings": warnings, "checks": len(checks)},
        "checks": checks,
    }


def _render_text(report: dict[str, Any]) -> str:
    lines = [
        f"插件根: {report['plugin_root']}",
        f"工作区: {report['workspace_root']}",
        f"检查: {report['summary']['checks']} | 错误: {report['summary']['errors']} | 警告: {report['summary']['warnings']}",
    ]
    for item in report["checks"]:
        if item["status"] == "pass":
            continue
        label = "ERROR" if item["status"] == "fail" else "WARN"
        lines.append(f"[{label}] {item['name']}: {item['detail']}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="novel-creator-pro 插件体检")
    parser.add_argument("--root", default="", help="覆盖工作区根目录")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    workspace = Path(args.root).expanduser().resolve() if args.root else None
    report = inspect(workspace)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(_render_text(report))
    return 1 if report["summary"]["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
