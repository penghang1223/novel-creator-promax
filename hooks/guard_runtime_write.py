#!/usr/bin/env python3
"""Block direct writes to plugin assets and pipeline state.

Exit code 2 blocks the tool call and returns stderr to Claude.
Set NOVEL_PIPELINE_ACTIVE=1 for the official pipeline, or
NOVEL_ALLOW_STATE_WRITE=1 for an intentional manual repair.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path, PurePosixPath

if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PROTECTED_PATTERNS = (
    "摘要/*_passport.json",
    "摘要/*_summary.json",
    "素材/commits/*",
    "设定/真相文件/*",
    "novel_state.json",
    "追踪/时间线/*",
    "追踪/上下文.md",
    "追踪/伏笔.md",
    "追踪/角色状态/*",
)


def _roots() -> tuple[Path, Path]:
    plugin_raw = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.environ.get("NOVEL_PLUGIN_ROOT")
    workspace_raw = os.environ.get("NOVEL_WORKSPACE_ROOT") or os.environ.get("CLAUDE_PROJECT_DIR")
    plugin = Path(plugin_raw).expanduser() if plugin_raw else Path(__file__).resolve().parents[1]
    workspace = Path(workspace_raw).expanduser() if workspace_raw else plugin
    return plugin.resolve(), workspace.resolve()


def _relative(path: Path, root: Path) -> PurePosixPath | None:
    try:
        return PurePosixPath(path.resolve().relative_to(root).as_posix())
    except ValueError:
        return None


def _block(message: str) -> int:
    print(message, file=sys.stderr)
    return 2


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return 0

    tool_input = payload.get("tool_input", {}) if isinstance(payload, dict) else {}
    if not isinstance(tool_input, dict):
        return 0
    raw_path = tool_input.get("file_path") or tool_input.get("path") or ""
    if not isinstance(raw_path, str) or not raw_path.strip():
        return 0

    target = Path(raw_path).expanduser()
    if not target.is_absolute():
        target = Path.cwd() / target

    plugin, workspace = _roots()
    if os.environ.get("NOVEL_ALLOW_STATE_WRITE") == "1":
        return 0

    # Source repository: plugin and workspace are the same directory.
    # Editing plugin source is the explicit purpose of this mode; the
    # pipeline-state protections below still apply.
    source_repo = plugin == workspace

    if not source_repo:
        plugin_relative = _relative(target, plugin)
        if plugin_relative is not None:
            return _block(
                "[novel-creator-pro] 插件资产是只读的，禁止直接写入：\n"
                f"  {target}\n"
                "插件更新后旧目录会被清理。请把产物写到工作区 ${CLAUDE_PROJECT_DIR}。"
            )

    workspace_relative = _relative(target, workspace)
    if workspace_relative is None:
        return 0

    if os.environ.get("NOVEL_PIPELINE_ACTIVE") == "1":
        return 0

    for pattern in PROTECTED_PATTERNS:
        if workspace_relative.match(pattern):
            return _block(
                "[novel-creator-pro] 该文件由写章流水线维护，禁止直接写入：\n"
                f"  {workspace_relative}\n"
                "请通过 write_pipeline.py 或对应阶段脚本更新；"
                "确需人工修复时设置 NOVEL_ALLOW_STATE_WRITE=1。"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
