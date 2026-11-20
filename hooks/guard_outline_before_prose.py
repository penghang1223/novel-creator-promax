#!/usr/bin/env python3
"""Block first creation of a chapter prose file when its outline is missing.

Editing an existing chapter is always allowed. A new chapter file under
``novel_output/{platform}/{book}/正文/`` requires a matching file under
``细纲/``. Set ``NOVEL_PIPELINE_ACTIVE=1`` for the official pipeline or
``NOVEL_ALLOW_STATE_WRITE=1`` for an intentional manual repair.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _workspace() -> Path:
    raw = os.environ.get("NOVEL_WORKSPACE_ROOT") or os.environ.get("CLAUDE_PROJECT_DIR")
    return Path(raw).expanduser().resolve() if raw else Path.cwd().resolve()


def chapter_number(path: Path) -> int | None:
    name = path.name
    match = re.search(r"第(\d+)章", name)
    if match:
        return int(match.group(1))
    match = re.match(r"^(\d{1,4})[_-]", name)
    if match:
        return int(match.group(1))
    return None


def outline_exists(novel_dir: Path, chapter: int) -> bool:
    outline_dir = novel_dir / "细纲"
    if not outline_dir.is_dir():
        return False
    patterns = (
        f"第{chapter}章*",
        f"第{chapter:03d}章*",
        f"*{chapter:03d}*",
        f"*chapter*{chapter}*",
        f"*{chapter}*",
    )
    for pattern in patterns:
        for path in outline_dir.glob(pattern):
            if path.is_file() and path.suffix.lower() in {".md", ".txt", ".json", ".yaml", ".yml"}:
                return True
    return False


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return 0
    if not isinstance(payload, dict):
        return 0
    tool_input = payload.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return 0
    raw_path = tool_input.get("file_path") or tool_input.get("path") or ""
    if not isinstance(raw_path, str) or not raw_path.strip():
        return 0

    if os.environ.get("NOVEL_ALLOW_STATE_WRITE") == "1" or os.environ.get("NOVEL_PIPELINE_ACTIVE") == "1":
        return 0

    target = Path(raw_path).expanduser()
    if not target.is_absolute():
        target = Path.cwd() / target
    workspace = _workspace()
    try:
        relative = target.resolve().relative_to(workspace)
    except ValueError:
        return 0

    parts = relative.parts
    if len(parts) < 4 or parts[0] != "novel_output" or parts[-2] != "正文":
        return 0
    if target.exists():
        return 0

    chapter = chapter_number(target)
    if chapter is None:
        return 0

    novel_dir = target.parent.parent
    if outline_exists(novel_dir, chapter):
        return 0

    print(
        "[novel-creator-pro] 第"
        f"{chapter}章缺少细纲，禁止首次创建正文：\n"
        f"  {relative.as_posix()}\n"
        f"先在 {novel_dir / '细纲'} 下补齐本章细纲，"
        "或设置 NOVEL_ALLOW_STATE_WRITE=1 进行人工修复。",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
