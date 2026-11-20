"""Chapter workflow state machine and short-lived per-chapter lock."""

from __future__ import annotations

import json
import os
import socket
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .jsonio import now_iso

WORKFLOW_SCHEMA_VERSION = "1.0"
WORKFLOW_PHASES = ("pre", "draft", "audit", "truth", "quality", "memory", "commit")
LOCK_TTL_SECONDS = 6 * 60 * 60


def init_workflow() -> dict[str, Any]:
    return {
        "schema_version": WORKFLOW_SCHEMA_VERSION,
        "stage": "pre",
        "status": "pending",
        "last_completed_stage": "",
        "next_action": "pre",
        "attempts": {},
        "error": "",
        "updated_at": now_iso(),
    }


def ensure_workflow_shape(value: Any) -> dict[str, Any]:
    base = init_workflow()
    current = value if isinstance(value, dict) else {}
    merged = {**base, **current}
    attempts = current.get("attempts")
    merged["attempts"] = dict(attempts) if isinstance(attempts, dict) else {}
    merged["schema_version"] = WORKFLOW_SCHEMA_VERSION
    return merged


def transition(
    workflow: Any,
    stage: str,
    status: str,
    *,
    next_action: str = "",
    error: str = "",
) -> dict[str, Any]:
    """Return a new workflow state and increment the phase attempt counter."""
    if stage not in WORKFLOW_PHASES:
        raise ValueError(f"未知章节工作流阶段: {stage}")
    result = ensure_workflow_shape(workflow)
    attempts = result["attempts"]
    attempts[stage] = int(attempts.get(stage, 0) or 0) + 1
    previous_completed = str(result.get("last_completed_stage", ""))
    result.update(
        {
            "stage": stage,
            "status": status,
            "next_action": next_action or stage,
            "error": error,
            "updated_at": now_iso(),
        }
    )
    if status == "pass":
        result["last_completed_stage"] = stage
    elif previous_completed:
        result["last_completed_stage"] = previous_completed
    return result


def recommended_action(workflow: Any) -> str:
    return str(ensure_workflow_shape(workflow).get("next_action") or "pre")


def _lock_path(novel_dir: Path, chapter: int) -> Path:
    return novel_dir / "素材" / "runs" / f"chapter_{chapter:03d}.lock"


@contextmanager
def chapter_lock(novel_dir: Path, chapter: int) -> Iterator[None]:
    """Prevent two writers from mutating one chapter at the same time."""
    path = _lock_path(novel_dir, chapter)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "pid": os.getpid(),
        "host": socket.gethostname(),
        "chapter": chapter,
        "created_at": now_iso(),
    }
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        stale = False
        try:
            stale = time.time() - path.stat().st_mtime > LOCK_TTL_SECONDS
        except OSError:
            pass
        if stale:
            try:
                path.unlink()
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except OSError as retry_exc:
                raise RuntimeError(f"章节锁已存在且无法清理: {path}") from retry_exc
        else:
            owner = ""
            try:
                owner = json.dumps(json.loads(path.read_text(encoding="utf-8")), ensure_ascii=False)
            except (OSError, json.JSONDecodeError):
                owner = "锁文件内容不可读"
            raise RuntimeError(f"第{chapter}章正在被其他进程处理: {owner}") from exc

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        yield
    finally:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
