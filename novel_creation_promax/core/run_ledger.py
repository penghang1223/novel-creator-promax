"""Durable execution ledger for chapter pipeline subprocesses."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Iterable

from .jsonio import now_iso
from .paths import infer_chapter_number

LEDGER_SCHEMA_VERSION = "1.0"
LEDGER_RELATIVE_PATH = Path("素材") / "runs" / "pipeline_runs.jsonl"
OUTPUT_TAIL_LIMIT = 2000


def ledger_path(novel_dir: Path) -> Path:
    return novel_dir / LEDGER_RELATIVE_PATH


def _tail(value: str, limit: int = OUTPUT_TAIL_LIMIT) -> str:
    if len(value) <= limit:
        return value
    return f"…{value[-limit:]}"


def append_run(novel_dir: Path, record: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "run_id": record.get("run_id") or uuid.uuid4().hex[:12],
        **record,
    }
    path = ledger_path(novel_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return payload


def load_runs(novel_dir: Path, *, chapter: int | None = None) -> list[dict[str, Any]]:
    path = ledger_path(novel_dir)
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        if chapter is not None and payload.get("chapter") != chapter:
            continue
        records.append(payload)
    return records


def _option(cmd: Iterable[str], name: str) -> str:
    values = list(cmd)
    try:
        index = values.index(name)
    except ValueError:
        return ""
    return values[index + 1] if index + 1 < len(values) else ""


def infer_run_context(cmd: list[str]) -> tuple[Path | None, int | None]:
    novel_dir_value = _option(cmd, "--novel-dir")
    if novel_dir_value:
        novel_dir = Path(novel_dir_value)
    else:
        novel_dir = None
        for option in ("--chapter-file", "--input", "--output", "--json-output"):
            value = _option(cmd, option)
            if not value:
                continue
            candidate = Path(value)
            for parent in candidate.parents:
                if parent.name in {"正文", "摘要", "素材", "记忆", "memory"}:
                    novel_dir = parent.parent
                    break
            if novel_dir:
                break

    chapter_value = _option(cmd, "--chapter")
    chapter = int(chapter_value) if chapter_value.isdigit() else None
    if chapter is None:
        chapter_file = _option(cmd, "--chapter-file")
        if chapter_file:
            chapter = infer_chapter_number(chapter_file)
    return novel_dir, chapter


def record_subprocess(
    cmd: list[str],
    description: str,
    result: dict[str, Any],
    *,
    started_at: str,
    finished_at: str,
    duration_ms: int,
) -> dict[str, Any] | None:
    novel_dir, chapter = infer_run_context(cmd)
    if novel_dir is None:
        return None
    return append_run(
        novel_dir,
        {
            "run_id": uuid.uuid4().hex[:12],
            "chapter": chapter,
            "description": description,
            "status": result.get("status", ""),
            "returncode": result.get("returncode"),
            "command": cmd,
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_ms": duration_ms,
            "stdout_tail": _tail(str(result.get("stdout", ""))),
            "stderr_tail": _tail(str(result.get("stderr", ""))),
            "created_at": now_iso(),
        },
    )
