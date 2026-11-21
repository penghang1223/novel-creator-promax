"""Per-chapter snapshots: body + settings + state + commit."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from .jsonio import now_iso

BACKUP_ROOT = Path("素材") / "备份"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _chapter_files(novel_dir: Path, chapter: int, explicit: Path | None) -> list[Path]:
    if explicit is not None and explicit.is_file():
        return [explicit]
    pattern = re.compile(rf"第\s*0*{chapter}\s*章")
    found: list[Path] = []
    for directory in (novel_dir / "正文",):
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            if path.is_file() and path.suffix.lower() in {".md", ".txt"} and pattern.search(path.name):
                found.append(path)
    return found


def _copy(source: Path, destination: Path, files: list[dict[str, Any]], root: Path) -> None:
    if source.is_dir():
        for path in sorted(source.rglob("*")):
            if path.is_file():
                target = destination / path.relative_to(source)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
                files.append(
                    {
                        "path": target.relative_to(root).as_posix(),
                        "sha256": _sha256(target),
                        "size": target.stat().st_size,
                    }
                )
    elif source.is_file():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        files.append(
            {
                "path": destination.relative_to(root).as_posix(),
                "sha256": _sha256(destination),
                "size": destination.stat().st_size,
            }
        )


def snapshot_chapter(
    novel_dir: Path,
    chapter: int,
    *,
    reason: str = "",
    keep: int = 5,
    chapter_file: Path | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Copy one chapter's body, settings, state and commit into 素材/备份/."""
    novel_dir = Path(novel_dir).resolve()
    if chapter < 1:
        raise ValueError("chapter 必须是正整数")

    stamp = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    root = novel_dir / BACKUP_ROOT / f"chapter_{chapter:03d}_{stamp}"
    root.mkdir(parents=True, exist_ok=False)
    files: list[dict[str, Any]] = []

    for path in _chapter_files(novel_dir, chapter, chapter_file):
        _copy(path, root / "正文" / path.name, files, root)

    settings = novel_dir / "设定"
    if settings.is_dir():
        _copy(settings, root / "设定", files, root)

    summary_dir = novel_dir / "摘要"
    if summary_dir.is_dir():
        for path in sorted(summary_dir.glob(f"chapter_{chapter:03d}_*")):
            if path.is_file():
                _copy(path, root / "摘要" / path.name, files, root)

    memory = novel_dir / "记忆"
    if memory.is_dir():
        _copy(memory, root / "记忆", files, root)

    state = novel_dir / "novel_state.json"
    if state.is_file():
        _copy(state, root / "novel_state.json", files, root)

    commit = novel_dir / "素材" / "commits" / f"chapter_{chapter:03d}.commit.json"
    if commit.is_file():
        _copy(commit, root / "素材" / "commits" / commit.name, files, root)

    manifest = {
        "schema_version": "1.0",
        "chapter": chapter,
        "created_at": now_iso(),
        "reason": reason,
        "source": str(novel_dir),
        "files": files,
    }
    (root / "_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    pruned: list[str] = []
    if keep > 0:
        snapshots = sorted(
            path
            for path in (novel_dir / BACKUP_ROOT).glob(f"chapter_{chapter:03d}_*")
            if path.is_dir() and path != root
        )
        for old in snapshots[: max(0, len(snapshots) - (keep - 1))]:
            shutil.rmtree(old)
            pruned.append(old.name)

    return {
        "path": str(root),
        "chapter": chapter,
        "files": len(files),
        "pruned": pruned,
    }


def list_snapshots(novel_dir: Path, chapter: int | None = None) -> list[dict[str, Any]]:
    novel_dir = Path(novel_dir).resolve()
    root = novel_dir / BACKUP_ROOT
    if not root.is_dir():
        return []
    pattern = f"chapter_{chapter:03d}_*" if chapter else "chapter_*"
    results: list[dict[str, Any]] = []
    for path in sorted(root.glob(pattern)):
        if not path.is_dir():
            continue
        manifest = path / "_manifest.json"
        payload = {}
        if manifest.is_file():
            try:
                payload = json.loads(manifest.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                payload = {}
        results.append(
            {
                "path": str(path),
                "chapter": payload.get("chapter", ""),
                "created_at": payload.get("created_at", ""),
                "reason": payload.get("reason", ""),
                "files": len(payload.get("files", [])) if isinstance(payload.get("files"), list) else 0,
            }
        )
    return results
