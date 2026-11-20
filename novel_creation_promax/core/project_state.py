"""Canonical project state shape and safe migration helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .jsonio import load_json, now_iso, save_json

STATE_SCHEMA_VERSION = "2.0"


def ensure_state_shape(
    state: Any,
    *,
    title: str = "",
    platform: str = "",
) -> dict[str, Any]:
    """Return a lossless state object with the canonical top-level fields.

    Unknown fields are preserved. A legacy non-dict ``chapters`` value is moved
    to ``chapters_legacy`` instead of being discarded.
    """
    normalized = dict(state) if isinstance(state, dict) else {}

    normalized.setdefault("schema_version", STATE_SCHEMA_VERSION)
    normalized.setdefault("title", title)
    normalized.setdefault("platform", platform)
    normalized.setdefault("current_chapter", 0)
    normalized.setdefault("last_completed_chapter", 0)
    normalized.setdefault("word_count", 0)
    normalized.setdefault("revision_history", [])
    normalized.setdefault("audit_history", [])
    normalized.setdefault("audit_coverage", {})
    normalized.setdefault("publish_state", {})
    normalized.setdefault("workflow_gate", {})
    normalized.setdefault("resume_point", {})
    normalized.setdefault("chapter_edit_status", {})
    normalized.setdefault("tension_contract", {"enabled": False})
    if not isinstance(normalized.get("tension_contract"), dict):
        normalized["tension_contract"] = {"enabled": False}
    normalized.setdefault("retrieval_backend", "lexical")
    if normalized.get("retrieval_backend") not in {"lexical", "tfidf"}:
        normalized["retrieval_backend"] = "lexical"

    for key in ("revision_history", "audit_history"):
        if not isinstance(normalized.get(key), list):
            if key in normalized:
                normalized.setdefault(f"{key}_legacy", normalized[key])
            normalized[key] = []
    for key in ("audit_coverage", "publish_state", "workflow_gate", "resume_point", "chapter_edit_status"):
        if not isinstance(normalized.get(key), dict):
            if key in normalized:
                normalized.setdefault(f"{key}_legacy", normalized[key])
            normalized[key] = {}

    chapters = normalized.get("chapters")
    if chapters is None:
        normalized["chapters"] = {}
    elif not isinstance(chapters, dict):
        normalized.setdefault("chapters_legacy", chapters)
        normalized["chapters"] = {}

    return normalized


def load_state(novel_dir: Path) -> dict[str, Any]:
    """Load and normalize one project's state without writing it back."""
    state = load_json(novel_dir / "novel_state.json", {})
    return ensure_state_shape(state, title=novel_dir.name, platform=novel_dir.parent.name)


def migrate_state_file(novel_dir: Path, *, apply: bool = False) -> dict[str, Any]:
    """Preview or apply a state migration; applying always creates a backup."""
    state_path = novel_dir / "novel_state.json"
    original = load_json(state_path, None)
    if not isinstance(original, dict):
        return {"novel_dir": str(novel_dir), "error": "novel_state.json 不是对象或不存在"}

    normalized = ensure_state_shape(original, title=novel_dir.name, platform=novel_dir.parent.name)
    normalized["schema_version"] = STATE_SCHEMA_VERSION
    changed_keys = sorted(key for key in set(original) | set(normalized) if original.get(key) != normalized.get(key))

    backup = ""
    if apply and changed_keys:
        stamp = now_iso().replace(":", "").replace("-", "")
        backup_path = novel_dir / "素材" / "state_backups" / f"novel_state.json.bak-{stamp}"
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        backup_path.write_bytes(state_path.read_bytes())
        save_json(state_path, normalized)
        backup = str(backup_path)

    return {
        "novel_dir": str(novel_dir),
        "changed_keys": changed_keys,
        "applied": bool(apply and changed_keys),
        "backup": backup,
    }
