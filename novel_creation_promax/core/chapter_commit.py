"""Chapter-level commit ledger for binding prose and pipeline artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .jsonio import load_json, now_iso
from .paths import rel

COMMIT_SCHEMA_VERSION = "1.0"
COMMIT_DIR = "素材/commits"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def commit_path(novel_dir: Path, chapter: int) -> Path:
    return novel_dir / COMMIT_DIR / f"chapter_{chapter:03d}.commit.json"


def remove_chapter_commit(novel_dir: Path, chapter: int) -> None:
    commit_path(novel_dir, chapter).unlink(missing_ok=True)


def commit_id_for(chapter: int, chapter_file: Path) -> str:
    return f"ch{chapter:03d}-{sha256_file(chapter_file)[:16]}"


def _artifact_snapshot(path: Path | None, novel_dir: Path, *, required: bool) -> dict[str, Any]:
    if path is None:
        return {"path": "", "sha256": "", "size": 0, "required": required, "exists": False}
    path = Path(path)
    snapshot: dict[str, Any] = {
        "path": rel(path, novel_dir),
        "sha256": "",
        "size": 0,
        "required": required,
        "exists": path.is_file(),
    }
    if path.is_file():
        snapshot["sha256"] = sha256_file(path)
        snapshot["size"] = path.stat().st_size
    return snapshot


def _resolve_artifact(novel_dir: Path, snapshot: dict[str, Any]) -> Path:
    stored_path = str(snapshot.get("path", ""))
    path = Path(stored_path)
    return path if path.is_absolute() else novel_dir / path


def load_commit(novel_dir: Path, chapter: int) -> dict[str, Any] | None:
    payload = load_json(commit_path(novel_dir, chapter), {})
    return payload if isinstance(payload, dict) else None


def _save_commit(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def record_chapter_commit(
    novel_dir: Path,
    chapter: int,
    *,
    chapter_file: Path,
    artifacts: dict[str, Path | None],
    pipeline: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write an accepted commit after all required chapter checks pass."""
    if not chapter_file.is_file():
        raise FileNotFoundError(f"章节正文不存在: {chapter_file}")
    if "chapter" not in artifacts:
        raise ValueError("提交记录必须包含 chapter artifact")

    snapshots = {
        name: _artifact_snapshot(path, novel_dir, required=path is not None)
        for name, path in artifacts.items()
    }
    missing = [name for name, item in snapshots.items() if item["required"] and not item["exists"]]
    if missing:
        raise FileNotFoundError(f"提交记录缺少必需文件: {', '.join(missing)}")

    parent = load_commit(novel_dir, chapter - 1) if chapter > 1 else None
    payload = {
        "schema_version": COMMIT_SCHEMA_VERSION,
        "commit_id": commit_id_for(chapter, chapter_file),
        "chapter": chapter,
        "status": "accepted",
        "created_at": now_iso(),
        "chapter_file": rel(chapter_file, novel_dir),
        "parent_commit": parent.get("commit_id", "") if parent else "",
        "artifacts": snapshots,
        "pipeline": pipeline or {},
        "verification": {
            "status": "valid",
            "checked_at": now_iso(),
        },
    }
    _save_commit(commit_path(novel_dir, chapter), payload)
    return payload


def verify_chapter_commit(novel_dir: Path, chapter: int) -> tuple[bool, str]:
    payload = load_commit(novel_dir, chapter)
    if not payload:
        return False, f"第{chapter}章缺少提交记录"
    if payload.get("status") != "accepted":
        return False, f"第{chapter}章提交状态为 {payload.get('status', 'unknown')}"
    if payload.get("schema_version") != COMMIT_SCHEMA_VERSION:
        return False, f"第{chapter}章提交记录版本不支持: {payload.get('schema_version')}"
    if payload.get("chapter") != chapter:
        return False, f"提交记录章号不匹配: expected={chapter}, actual={payload.get('chapter')}"

    problems: list[str] = []
    artifacts = payload.get("artifacts", {})
    if not isinstance(artifacts, dict):
        return False, f"第{chapter}章提交记录缺少 artifacts"

    for name, snapshot in artifacts.items():
        if not isinstance(snapshot, dict):
            problems.append(f"{name} 快照格式无效")
            continue
        required = bool(snapshot.get("required", True))
        path = _resolve_artifact(novel_dir, snapshot)
        try:
            path.resolve().relative_to(novel_dir.resolve())
        except ValueError:
            problems.append(f"{name} 路径越界: {snapshot.get('path', '')}")
            continue
        if not path.is_file():
            if required:
                problems.append(f"{name} 不存在: {snapshot.get('path', '')}")
            continue
        expected_hash = str(snapshot.get("sha256", ""))
        if not expected_hash or sha256_file(path) != expected_hash:
            problems.append(f"{name} 指纹不匹配: {snapshot.get('path', '')}")
        expected_size = snapshot.get("size")
        if isinstance(expected_size, int) and path.stat().st_size != expected_size:
            problems.append(f"{name} 大小不匹配: {snapshot.get('path', '')}")

    expected_commit_id = str(payload.get("commit_id", ""))
    chapter_snapshot = artifacts.get("chapter", {})
    stored_hash = chapter_snapshot.get("sha256") if isinstance(chapter_snapshot, dict) else ""
    if expected_commit_id != f"ch{chapter:03d}-{str(stored_hash)[:16]}":
        problems.append("commit_id 与正文指纹不匹配")

    if problems:
        return False, f"第{chapter}章提交记录校验失败: {'；'.join(problems)}"
    return True, f"第{chapter}章提交记录有效 ({payload.get('commit_id', '')})"
