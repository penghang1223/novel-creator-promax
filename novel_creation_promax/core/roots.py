"""Resolve plugin assets and user workspace paths.

Two roots exist at runtime:

* ``plugin_root`` - read-only assets shipped with the plugin (skills,
  references, knowledge base, scripts). Claude Code exposes it as
  ``CLAUDE_PLUGIN_ROOT``. It changes on every plugin update, so nothing may be
  written there.
* ``workspace_root`` - the user's writing project (``novel_output/``,
  ``MEMORY.md``, ``.claude/memory/``). Claude Code exposes it as
  ``CLAUDE_PROJECT_DIR``.

When running from the source repository both roots are the same directory, so
existing behavior is preserved.
"""

from __future__ import annotations

import os
from pathlib import Path

WORKSPACE_PREFIXES = ("novel_output", ".claude")
WORKSPACE_FILES = {"MEMORY.md"}


def plugin_root() -> Path:
    raw = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.environ.get("NOVEL_PLUGIN_ROOT")
    if raw:
        return Path(raw).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


def workspace_root() -> Path:
    raw = os.environ.get("NOVEL_WORKSPACE_ROOT") or os.environ.get("CLAUDE_PROJECT_DIR")
    if raw:
        return Path(raw).expanduser().resolve()
    return plugin_root()


def _safe_join(root: Path, relative: str | Path) -> Path:
    relative_path = Path(relative)
    if relative_path.is_absolute():
        return relative_path.resolve()
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"路径越界: {relative}") from exc
    return candidate


def asset_path(relative: str | Path) -> Path:
    relative_path = Path(relative)
    if relative_path.is_absolute():
        return relative_path.resolve()
    if relative_path.parts and relative_path.parts[0] == "knowledge_base":
        override = workspace_root() / relative_path
        if override.exists():
            return override.resolve()
    return _safe_join(plugin_root(), relative_path)


def workspace_path(relative: str | Path) -> Path:
    return _safe_join(workspace_root(), relative)


def _inferred_scope(path: str) -> str:
    normalized = path.replace("\\", "/")
    if normalized in WORKSPACE_FILES or normalized.startswith("MEMORY.md/"):
        return "workspace"
    if any(normalized == prefix or normalized.startswith(prefix + "/") for prefix in WORKSPACE_PREFIXES):
        return "workspace"
    return "plugin"


def resolve_route_path(path: str | Path, scope: str = "") -> Path:
    """Resolve one ``_ROUTES.json`` path to an absolute path."""
    path_text = str(path)
    if Path(path_text).is_absolute():
        return Path(path_text).resolve()

    effective_scope = scope if scope in {"plugin", "workspace"} else _inferred_scope(path_text)
    if effective_scope == "workspace":
        return workspace_path(path_text)
    return asset_path(path_text)
