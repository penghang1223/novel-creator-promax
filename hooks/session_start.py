#!/usr/bin/env python3
"""Print a compact workspace status at session start.

Read-only: never creates or modifies project files.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from novel_creation_promax.core import workspace_confirmation as wc  # noqa: E402


def _read_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _roots() -> tuple[Path, Path]:
    plugin_raw = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.environ.get("NOVEL_PLUGIN_ROOT")
    workspace_raw = os.environ.get("NOVEL_WORKSPACE_ROOT") or os.environ.get("CLAUDE_PROJECT_DIR")
    plugin = Path(plugin_raw).expanduser() if plugin_raw else Path(__file__).resolve().parents[1]
    workspace = Path(workspace_raw).expanduser() if workspace_raw else plugin
    return plugin.resolve(), workspace.resolve()


def _books(workspace: Path) -> list[dict]:
    books: list[dict] = []
    output = workspace / "novel_output"
    if not output.is_dir():
        return books
    for platform_dir in sorted(output.iterdir()):
        if not platform_dir.is_dir() or platform_dir.name.startswith((".", "_", "archive")):
            continue
        for novel_dir in sorted(platform_dir.iterdir()):
            if not novel_dir.is_dir() or novel_dir.name.startswith((".", "_")):
                continue
            state_path = novel_dir / "novel_state.json"
            if not state_path.is_file():
                continue
            state = _read_json(state_path)
            books.append(
                {
                    "platform": platform_dir.name,
                    "title": str(state.get("title") or novel_dir.name),
                    "chapter": int(state.get("current_chapter", 0) or 0),
                    "completed": int(state.get("last_completed_chapter", 0) or 0),
                }
            )
    return books


def _optional_deps() -> list[str]:
    missing: list[str] = []
    for module, label in (
        ("PIL", "Pillow"),
        ("jieba", "jieba"),
        ("requests", "requests"),
    ):
        if importlib.util.find_spec(module) is None:
            missing.append(label)
    return missing


def main() -> int:
    try:
        json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        pass

    plugin, workspace = _roots()
    books = _books(workspace)
    lines = [f"[novel-creator-pro] workspace={workspace}"]
    try:
        lines.append(wc.format_status(wc.status(workspace)))
    except (OSError, ValueError):
        pass

    if books:
        preview = ", ".join(
            f"{item['title']}({item['platform']}) 第{item['chapter']}章" for item in books[:3]
        )
        suffix = f" 等 {len(books)} 本" if len(books) > 3 else ""
        lines.append(f"书籍: {preview}{suffix}")
    else:
        lines.append("书籍: 未发现 novel_output/{平台}/{书名}/novel_state.json")

    preferences = workspace / ".claude" / "memory" / "decisions" / "preferences.md"
    if preferences.is_file():
        lines.append("共享记忆: 已发现 .claude/memory/decisions/preferences.md")

    rules = plugin / "novel_creation_promax" / "SKILL.md"
    lines.append(f"规则: 小说任务前先读 {rules} 的「行为红线」。")

    if sys.version_info < (3, 10):
        lines.append(f"提示: Python {sys.version.split()[0]}，建议 3.10+")

    missing = _optional_deps()
    if missing:
        lines.append(f"可选依赖未安装: {', '.join(missing)}（仅封面/分词/网络相关功能受影响）")

    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
