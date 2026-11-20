"""Snapshot and review queue primitives for safe chapter revisions."""

from __future__ import annotations

import difflib
import hashlib
import json
import shutil
import uuid
from pathlib import Path
from typing import Any

from .chapter_commit import commit_path, remove_chapter_commit
from .chapter_workflow import transition
from .jsonio import load_json, now_iso, save_json
from .passport import load_passport, passport_path, save_passport
from .paths import find_chapter_file, rel
from .project_state import ensure_state_shape


REVISION_SCHEMA_VERSION = "1.0"
REVISION_ROOT = Path("素材") / "revisions"
DIRTY_PIPELINE_STAGES = (
    "pre_write_check",
    "writing_gate",
    "post_write_audit",
    "normalizer",
    "truth_delta",
    "truth_sync",
    "memory_sync",
)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _revision_dir(novel_dir: Path, chapter: int, kind: str, revision_id: str) -> Path:
    if kind not in {"snapshots", "proposals"}:
        raise ValueError(f"不支持的 revision 类型: {kind}")
    return novel_dir / REVISION_ROOT / f"chapter_{chapter:03d}" / kind / revision_id


def _safe_revision_id(value: str) -> str:
    if not value or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for char in value):
        raise ValueError(f"非法 revision id: {value}")
    return value


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def _snapshot_candidates(novel_dir: Path, chapter: int, chapter_file: Path) -> list[Path]:
    candidates = [chapter_file, passport_path(novel_dir, chapter), novel_dir / "novel_state.json", commit_path(novel_dir, chapter)]
    candidates.extend(
        [
            novel_dir / "摘要" / f"chapter_{chapter:03d}_truth_delta.json",
            novel_dir / "素材" / f"truth_delta_ch{chapter:03d}.json",
            novel_dir / "素材" / f"truth_apply_ch{chapter:03d}.json",
        ]
    )
    return [path for path in candidates if path.is_file()]


def create_snapshot(
    novel_dir: Path,
    chapter: int,
    *,
    reason: str,
    source: str = "unknown",
) -> dict[str, Any]:
    """Copy mutable chapter artifacts before a revision or restore."""
    chapter_file = find_chapter_file(novel_dir, chapter)
    if chapter_file is None:
        raise FileNotFoundError(f"未找到第{chapter}章正文")
    snapshot_id = f"{now_iso().replace(':', '').replace('-', '')}-{uuid.uuid4().hex[:8]}"
    target = _revision_dir(novel_dir, chapter, "snapshots", snapshot_id)
    files: list[dict[str, Any]] = []
    for path in _snapshot_candidates(novel_dir, chapter, chapter_file):
        relative = path.relative_to(novel_dir)
        destination = target / "files" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        files.append(
            {
                "path": relative.as_posix(),
                "snapshot_path": destination.relative_to(target).as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "size": path.stat().st_size,
            }
        )
    manifest = {
        "schema_version": REVISION_SCHEMA_VERSION,
        "type": "snapshot",
        "snapshot_id": snapshot_id,
        "chapter": chapter,
        "reason": reason,
        "source": source,
        "created_at": now_iso(),
        "files": files,
    }
    save_json(target / "manifest.json", manifest)
    return manifest


def create_proposal(
    novel_dir: Path,
    chapter: int,
    proposed_content: str,
    *,
    reason: str,
    source: str = "unknown",
) -> dict[str, Any]:
    """Create a pending text proposal without modifying the manuscript."""
    chapter_file = find_chapter_file(novel_dir, chapter)
    if chapter_file is None:
        raise FileNotFoundError(f"未找到第{chapter}章正文")
    current_content = chapter_file.read_text(encoding="utf-8")
    proposal_id = f"{now_iso().replace(':', '').replace('-', '')}-{uuid.uuid4().hex[:8]}"
    target = _revision_dir(novel_dir, chapter, "proposals", proposal_id)
    _write_text_atomic(target / "proposed.md", proposed_content)
    diff = difflib.unified_diff(
        current_content.splitlines(keepends=True),
        proposed_content.splitlines(keepends=True),
        fromfile=f"current/{chapter_file.name}",
        tofile=f"proposal/{chapter_file.name}",
    )
    _write_text_atomic(target / "proposal.diff", "".join(diff))
    manifest = {
        "schema_version": REVISION_SCHEMA_VERSION,
        "type": "proposal",
        "proposal_id": proposal_id,
        "chapter": chapter,
        "status": "pending",
        "reason": reason,
        "source": source,
        "created_at": now_iso(),
        "chapter_path": rel(chapter_file, novel_dir),
        "base_sha256": sha256_text(current_content),
        "proposed_sha256": sha256_text(proposed_content),
        "proposal_path": f"{(target / 'proposed.md').relative_to(novel_dir).as_posix()}",
        "diff_path": f"{(target / 'proposal.diff').relative_to(novel_dir).as_posix()}",
    }
    save_json(target / "manifest.json", manifest)
    return manifest


def _find_revision_dir(novel_dir: Path, chapter: int, kind: str, revision_id: str) -> Path:
    return _revision_dir(novel_dir, chapter, kind, _safe_revision_id(revision_id))


def list_proposals(novel_dir: Path, chapter: int | None = None) -> list[dict[str, Any]]:
    root = novel_dir / REVISION_ROOT
    chapter_dirs = [root / f"chapter_{chapter:03d}"] if chapter is not None else sorted(root.glob("chapter_*"))
    results: list[dict[str, Any]] = []
    for chapter_dir in chapter_dirs:
        for manifest_path in sorted((chapter_dir / "proposals").glob("*/manifest.json")):
            payload = load_json(manifest_path, {})
            if isinstance(payload, dict):
                results.append(payload)
    return results


def _mark_chapter_dirty(novel_dir: Path, chapter: int, reason: str) -> None:
    chapter_file = find_chapter_file(novel_dir, chapter)
    passport = load_passport(novel_dir, chapter, chapter_file.stem if chapter_file else "", chapter_file)
    for stage in DIRTY_PIPELINE_STAGES:
        passport["pipeline"][stage] = "pending"
    passport["pipeline_result"] = "pending"
    passport["workflow"] = transition(
        passport.get("workflow", {}),
        "draft",
        "pending",
        next_action="post --phase audit",
        error=reason,
    )
    passport["inputs"]["revision_source"] = reason
    save_passport(novel_dir, chapter, passport)

    state_path = novel_dir / "novel_state.json"
    state = ensure_state_shape(load_json(state_path, {}), title=novel_dir.name, platform=novel_dir.parent.name)
    state.setdefault("chapter_edit_status", {})[f"{chapter:03d}"] = {
        "status": "dirty",
        "source": "revision_control",
        "updated_at": now_iso(),
    }
    state["resume_point"] = {
        "action": "post --phase audit",
        "chapter": chapter,
        "next_chapter": chapter,
        "hint": reason,
        "updated_at": now_iso(),
    }
    state["updated_at"] = now_iso()
    save_json(state_path, state)
    remove_chapter_commit(novel_dir, chapter)


def review_proposal(novel_dir: Path, chapter: int, proposal_id: str, *, approve: bool) -> dict[str, Any]:
    """Approve or reject one proposal, refusing stale-base overwrites."""
    target = _find_revision_dir(novel_dir, chapter, "proposals", proposal_id)
    manifest_path = target / "manifest.json"
    manifest = load_json(manifest_path, {})
    if not isinstance(manifest, dict) or manifest.get("type") != "proposal":
        raise FileNotFoundError(f"proposal 不存在: {proposal_id}")
    if manifest.get("status") != "pending":
        raise RuntimeError(f"proposal 当前状态不可审核: {manifest.get('status')}")
    chapter_file = find_chapter_file(novel_dir, chapter)
    if chapter_file is None:
        raise FileNotFoundError(f"未找到第{chapter}章正文")
    current_content = chapter_file.read_text(encoding="utf-8")
    if sha256_text(current_content) != manifest.get("base_sha256"):
        manifest.update({"status": "stale", "reviewed_at": now_iso(), "review_note": "正文已变化，拒绝覆盖新版本"})
        save_json(manifest_path, manifest)
        raise RuntimeError("proposal 基线已失效，请基于最新正文重新生成")

    if not approve:
        manifest.update({"status": "rejected", "reviewed_at": now_iso()})
        save_json(manifest_path, manifest)
        return manifest

    snapshot = create_snapshot(novel_dir, chapter, reason=f"批准 revision {proposal_id} 前快照", source="revision_control")
    proposed_path = target / "proposed.md"
    proposed_content = proposed_path.read_text(encoding="utf-8")
    _write_text_atomic(chapter_file, proposed_content)
    _mark_chapter_dirty(novel_dir, chapter, f"已批准 revision proposal {proposal_id}，需重新执行 post")
    manifest.update(
        {
            "status": "approved",
            "reviewed_at": now_iso(),
            "snapshot_id": snapshot["snapshot_id"],
            "applied_sha256": sha256_text(proposed_content),
        }
    )
    save_json(manifest_path, manifest)
    return manifest


def restore_snapshot(novel_dir: Path, chapter: int, snapshot_id: str) -> dict[str, Any]:
    """Restore a snapshot and mark the chapter dirty for post validation."""
    target = _find_revision_dir(novel_dir, chapter, "snapshots", snapshot_id)
    manifest = load_json(target / "manifest.json", {})
    if not isinstance(manifest, dict) or manifest.get("type") != "snapshot":
        raise FileNotFoundError(f"snapshot 不存在: {snapshot_id}")
    for item in manifest.get("files", []):
        if not isinstance(item, dict):
            continue
        source = target / str(item.get("snapshot_path", ""))
        destination = novel_dir / str(item.get("path", ""))
        if not source.is_file():
            raise FileNotFoundError(f"snapshot 文件不存在: {source}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    _mark_chapter_dirty(novel_dir, chapter, f"已恢复 snapshot {snapshot_id}，需重新执行 post")
    return manifest
