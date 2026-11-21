"""Workspace output-location confirmation.

``workspace_root()`` answers "where did Claude Code start"; this module answers
"may we write novel products there?". The decision is recorded in
``.novel-workspace.json`` at the workspace root so it travels with the folder
but still invalidates when the folder is moved.

Read-only: :func:`status` never writes. :func:`confirm` is the only writer;
pipeline entry points call :func:`require_confirmed` before their first write.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .jsonio import now_iso
from .roots import plugin_root, workspace_root

MARKER_NAME = ".novel-workspace.json"
SCHEMA_VERSION = "1.0"
BLOCKED_DANGEROUS = {"plugin_root", "root"}

WRITE_PATHS_HINT = (
    "novel_output/{平台}/{书名}/",
    "素材/调研/",
    "创意/",
    "创意库/",
    "MEMORY.md",
    ".claude/memory/",
    "knowledge_base/80_Projects/",
)


class WorkspaceConfirmationError(RuntimeError):
    """Base error carrying the status payload and a user-facing message."""

    def __init__(self, message: str, status: dict[str, Any]):
        super().__init__(message)
        self.status = status


class WorkspaceNotConfirmed(WorkspaceConfirmationError):
    """Raised when a write entry point hits an unconfirmed workspace."""


def marker_path(workspace: Path) -> Path:
    return Path(workspace).expanduser().resolve() / MARKER_NAME


def _dangerous(workspace: Path) -> str:
    resolved = workspace.expanduser().resolve()
    if resolved == plugin_root().resolve():
        return "plugin_root"
    if resolved == Path("/").resolve():
        return "root"
    if resolved == Path.home().resolve():
        return "home"
    return ""


def _legacy_books(workspace: Path) -> int:
    output = Path(workspace) / "novel_output"
    if not output.is_dir():
        return 0
    return sum(1 for path in output.glob("*/*/novel_state.json") if path.is_file())


def status(workspace: Path | str | None = None) -> dict[str, Any]:
    """Return the confirmation state without touching disk."""
    root = Path(workspace).expanduser().resolve() if workspace else workspace_root().resolve()
    dangerous = _dangerous(root)
    marker = marker_path(root)
    confirmed = False
    reason = "missing"

    if dangerous in BLOCKED_DANGEROUS:
        reason = dangerous
    elif not marker.is_file():
        reason = "missing"
    else:
        try:
            payload = json.loads(marker.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            payload = None
        if not isinstance(payload, dict) or not payload:
            reason = "invalid"
        elif payload.get("confirmed") is not True:
            reason = "invalid"
        elif str(payload.get("workspace", "")) != str(root):
            reason = "path_mismatch"
        else:
            confirmed = True
            reason = "ok"

    return {
        "workspace": str(root),
        "confirmed": confirmed,
        "reason": reason,
        "legacy_books": _legacy_books(root),
        "dangerous": dangerous,
        "marker": str(marker),
        "write_paths": list(WRITE_PATHS_HINT),
    }


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=str(path.parent), prefix=".novel-workspace-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def confirm(workspace: Path | str | None = None, *, by: str = "user") -> dict[str, Any]:
    """Record the user's approval of this workspace. Blocked roots raise."""
    root = Path(workspace).expanduser().resolve() if workspace else workspace_root().resolve()
    current = status(root)
    if current["dangerous"] in BLOCKED_DANGEROUS:
        raise WorkspaceConfirmationError(refusal_message(current), current)

    _atomic_write_json(
        marker_path(root),
        {
            "schema_version": SCHEMA_VERSION,
            "confirmed": True,
            "workspace": str(root),
            "confirmed_at": now_iso(),
            "confirmed_by": by,
        },
    )
    return status(root)


def forget(workspace: Path | str | None = None) -> bool:
    """Remove the marker. Returns True when a marker existed."""
    path = marker_path(Path(workspace).expanduser() if workspace else workspace_root())
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False


def refusal_message(payload: dict[str, Any]) -> str:
    root = payload["workspace"]
    dangerous = payload.get("dangerous", "")
    if dangerous == "plugin_root":
        return (
            "当前目录是插件资产根，不能作为写作工作区：\n"
            f"  {root}\n"
            "请在一个独立的写作目录打开 Claude Code，或设置 NOVEL_WORKSPACE_ROOT。"
        )
    if dangerous == "root":
        return (
            "不能把文件系统根目录 / 作为写作工作区。\n"
            "请选择一个专用的写作目录后重新打开 Claude Code。"
        )
    if payload.get("reason") == "path_mismatch":
        return (
            "工作区确认标记与当前位置不一致（目录可能被移动或复制）：\n"
            f"  {root}\n"
            "请确认后将重新写入标记：\n"
            "  python3 tools/workspace.py confirm"
        )
    return (
        "工作区尚未确认，拒绝写入：\n"
        f"  {root}\n"
        "将创建/写入：\n"
        + "\n".join(f"  - {item}" for item in WRITE_PATHS_HINT)
        + "\n确认后运行：\n"
        "  python3 tools/workspace.py confirm\n"
        "若地址不对，请在目标目录重新打开 Claude Code 后再确认。"
    )


def require_confirmed(
    workspace: Path | str | None = None,
    *,
    allow_legacy: bool = True,
) -> dict[str, Any]:
    """Return confirmed status, auto-confirming legacy workspaces with books.

    Raises :class:`WorkspaceNotConfirmed` when no marker and no legacy books.
    The returned payload has ``auto_confirmed=True`` when a legacy marker was
    written by this call.
    """
    current = status(workspace)
    if current["confirmed"]:
        return current

    if (
        allow_legacy
        and current["legacy_books"] > 0
        and current["dangerous"] not in BLOCKED_DANGEROUS
    ):
        confirmed = confirm(current["workspace"], by="legacy")
        confirmed["auto_confirmed"] = True
        return confirmed

    raise WorkspaceNotConfirmed(refusal_message(current), current)


def format_status(payload: dict[str, Any]) -> str:
    """Human-readable status used by the CLI and the session hook."""
    if payload["dangerous"] == "plugin_root":
        return f"工作区: 插件资产根，不能写入创作产物 ({payload['workspace']})"
    if payload["dangerous"] == "root":
        return "工作区: 文件系统根目录，不能写入创作产物"
    if payload["confirmed"]:
        suffix = "（家目录）" if payload["dangerous"] == "home" else ""
        return f"工作区: 已确认 {payload['workspace']}{suffix}"
    if payload["legacy_books"] > 0:
        return (
            f"工作区: 已识别 {payload['legacy_books']} 本存量书，"
            "将在下次写入时补确认"
        )
    home_warning = "（家目录：产物会散落在 home 下）" if payload["dangerous"] == "home" else ""
    return (
        f"工作区: 未确认 {payload['workspace']}{home_warning} — "
        "首次创作前需确认产物保存位置"
    )
