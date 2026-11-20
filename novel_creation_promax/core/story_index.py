"""SQLite read model for project and chapter discovery.

JSON, Markdown, passport, and commit files remain the source of truth. This
module only builds a disposable query index for dashboards and reports.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable

from .chapter_commit import commit_path
from .jsonio import load_json, now_iso
from .passport import passport_path
from .paths import count_chinese_chars, extract_chapter_title, list_chapter_files, rel


INDEX_SCHEMA_VERSION = "1.0"
INDEX_RELATIVE_PATH = Path("novel_output") / "_workspace" / "index" / "story_index.sqlite3"


def index_path(project_root: Path) -> Path:
    return project_root / INDEX_RELATIVE_PATH


def project_key(project_root: Path, novel_dir: Path) -> str:
    return rel(novel_dir.resolve(), project_root.resolve())


def _relative_path(project_root: Path, path: Path | None) -> str:
    return rel(path, project_root) if path else ""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS projects (
            project_key TEXT PRIMARY KEY,
            novel_dir TEXT NOT NULL,
            title TEXT NOT NULL,
            platform TEXT NOT NULL,
            state_updated_at TEXT NOT NULL DEFAULT '',
            current_chapter INTEGER NOT NULL DEFAULT 0,
            last_completed_chapter INTEGER NOT NULL DEFAULT 0,
            word_count INTEGER NOT NULL DEFAULT 0,
            chapter_count INTEGER NOT NULL DEFAULT 0,
            state_mtime_ns INTEGER NOT NULL DEFAULT 0,
            source_mtime_ns INTEGER NOT NULL DEFAULT 0,
            indexed_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS chapters (
            project_key TEXT NOT NULL,
            chapter_number INTEGER NOT NULL,
            title TEXT NOT NULL,
            chapter_path TEXT NOT NULL,
            word_count INTEGER NOT NULL DEFAULT 0,
            chapter_mtime_ns INTEGER NOT NULL DEFAULT 0,
            passport_path TEXT NOT NULL DEFAULT '',
            passport_mtime_ns INTEGER NOT NULL DEFAULT 0,
            summary_path TEXT NOT NULL DEFAULT '',
            summary_mtime_ns INTEGER NOT NULL DEFAULT 0,
            pipeline_result TEXT NOT NULL DEFAULT 'pending',
            workflow_stage TEXT NOT NULL DEFAULT '',
            workflow_status TEXT NOT NULL DEFAULT 'pending',
            last_completed_stage TEXT NOT NULL DEFAULT '',
            next_action TEXT NOT NULL DEFAULT '',
            writing_gate TEXT NOT NULL DEFAULT 'pending',
            post_write_audit TEXT NOT NULL DEFAULT 'pending',
            truth_delta TEXT NOT NULL DEFAULT 'pending',
            truth_sync TEXT NOT NULL DEFAULT 'pending',
            memory_sync TEXT NOT NULL DEFAULT 'pending',
            commit_path TEXT NOT NULL DEFAULT '',
            commit_status TEXT NOT NULL DEFAULT 'missing',
            updated_at TEXT NOT NULL DEFAULT '',
            indexed_at TEXT NOT NULL,
            PRIMARY KEY (project_key, chapter_number),
            FOREIGN KEY (project_key) REFERENCES projects(project_key) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_chapters_workflow
            ON chapters(workflow_status, workflow_stage);
        CREATE INDEX IF NOT EXISTS idx_chapters_pipeline
            ON chapters(pipeline_result, post_write_audit);
        CREATE INDEX IF NOT EXISTS idx_projects_platform
            ON projects(platform, title);
        """
    )
    connection.execute(
        """
        INSERT INTO metadata(key, value) VALUES('schema_version', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (INDEX_SCHEMA_VERSION,),
    )


def _stat_mtime(path: Path | None) -> int:
    if path is None:
        return 0
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return 0


def _state_payload(novel_dir: Path) -> dict[str, Any]:
    state = load_json(novel_dir / "novel_state.json", {})
    return state if isinstance(state, dict) else {}


def _pipeline_value(pipeline: dict[str, Any], key: str) -> str:
    value = pipeline.get(key, "pending")
    return str(value) if value is not None else "pending"


def _chapter_row(
    project_root: Path,
    novel_dir: Path,
    chapter: int,
    chapter_file: Path,
    *,
    indexed_at: str,
    previous: sqlite3.Row | None,
) -> dict[str, Any]:
    passport_file = passport_path(novel_dir, chapter)
    summary_file = novel_dir / "摘要" / f"chapter_{chapter:03d}_summary.json"
    commit_file = commit_path(novel_dir, chapter)
    chapter_mtime = _stat_mtime(chapter_file)
    passport_mtime = _stat_mtime(passport_file)
    summary_mtime = _stat_mtime(summary_file)
    commit_mtime = _stat_mtime(commit_file)

    unchanged = (
        previous is not None
        and previous["chapter_mtime_ns"] == chapter_mtime
        and previous["passport_mtime_ns"] == passport_mtime
        and previous["summary_mtime_ns"] == summary_mtime
        and previous["commit_path"] == _relative_path(project_root, commit_file)
        and ((previous["commit_status"] == "missing" and not commit_mtime)
             or (previous["commit_status"] != "missing" and commit_mtime))
    )
    if unchanged and previous is not None:
        return dict(previous)

    passport = load_json(passport_file, {})
    passport = passport if isinstance(passport, dict) else {}
    pipeline = passport.get("pipeline", {})
    pipeline = pipeline if isinstance(pipeline, dict) else {}
    workflow = passport.get("workflow", {})
    workflow = workflow if isinstance(workflow, dict) else {}
    commit = load_json(commit_file, {})
    commit = commit if isinstance(commit, dict) else {}
    state = _state_payload(novel_dir)
    return {
        "project_key": project_key(project_root, novel_dir),
        "chapter_number": chapter,
        "title": extract_chapter_title(chapter_file.name),
        "chapter_path": _relative_path(project_root, chapter_file),
        "word_count": count_chinese_chars(chapter_file.read_text(encoding="utf-8", errors="replace")),
        "chapter_mtime_ns": chapter_mtime,
        "passport_path": _relative_path(project_root, passport_file) if passport_file.is_file() else "",
        "passport_mtime_ns": passport_mtime,
        "summary_path": _relative_path(project_root, summary_file) if summary_file.is_file() else "",
        "summary_mtime_ns": summary_mtime,
        "pipeline_result": str(passport.get("pipeline_result", "pending")),
        "workflow_stage": str(workflow.get("stage", "")),
        "workflow_status": str(workflow.get("status", "pending")),
        "last_completed_stage": str(workflow.get("last_completed_stage", "")),
        "next_action": str(workflow.get("next_action", "")),
        "writing_gate": _pipeline_value(pipeline, "writing_gate"),
        "post_write_audit": _pipeline_value(pipeline, "post_write_audit"),
        "truth_delta": _pipeline_value(pipeline, "truth_delta"),
        "truth_sync": _pipeline_value(pipeline, "truth_sync"),
        "memory_sync": _pipeline_value(pipeline, "memory_sync"),
        "commit_path": _relative_path(project_root, commit_file) if commit_file.is_file() else "",
        "commit_status": str(commit.get("status", "missing")) if commit_file.is_file() else "missing",
        "updated_at": str(passport.get("updated_at") or state.get("updated_at") or ""),
        "indexed_at": indexed_at,
    }


def _upsert_project(
    connection: sqlite3.Connection,
    project_root: Path,
    novel_dir: Path,
    rows: list[dict[str, Any]],
    indexed_at: str,
) -> None:
    state = _state_payload(novel_dir)
    state_file = novel_dir / "novel_state.json"
    project = project_key(project_root, novel_dir)
    source_mtime = max([_stat_mtime(state_file), *(row["chapter_mtime_ns"] for row in rows)], default=0)
    word_count = sum(int(row["word_count"] or 0) for row in rows)
    connection.execute(
        """
        INSERT INTO projects(
            project_key, novel_dir, title, platform, state_updated_at,
            current_chapter, last_completed_chapter, word_count, chapter_count,
            state_mtime_ns, source_mtime_ns, indexed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(project_key) DO UPDATE SET
            novel_dir = excluded.novel_dir,
            title = excluded.title,
            platform = excluded.platform,
            state_updated_at = excluded.state_updated_at,
            current_chapter = excluded.current_chapter,
            last_completed_chapter = excluded.last_completed_chapter,
            word_count = excluded.word_count,
            chapter_count = excluded.chapter_count,
            state_mtime_ns = excluded.state_mtime_ns,
            source_mtime_ns = excluded.source_mtime_ns,
            indexed_at = excluded.indexed_at
        """,
        (
            project,
            _relative_path(project_root, novel_dir),
            str(state.get("title") or novel_dir.name),
            str(state.get("platform") or novel_dir.parent.name),
            str(state.get("updated_at") or ""),
            int(state.get("current_chapter", 0) or 0),
            int(state.get("last_completed_chapter", 0) or 0),
            word_count,
            len(rows),
            _stat_mtime(state_file),
            source_mtime,
            indexed_at,
        ),
    )


def sync_project(
    connection: sqlite3.Connection,
    project_root: Path,
    novel_dir: Path,
    *,
    indexed_at: str | None = None,
) -> dict[str, int | str]:
    """Incrementally sync one project into an existing connection."""
    project_root = project_root.resolve()
    novel_dir = novel_dir.resolve()
    timestamp = indexed_at or now_iso()
    key = project_key(project_root, novel_dir)
    previous = {
        row["chapter_number"]: row
        for row in connection.execute(
            "SELECT * FROM chapters WHERE project_key = ?", (key,)
        ).fetchall()
    }
    rows = [
        _chapter_row(
            project_root,
            novel_dir,
            chapter,
            chapter_file,
            indexed_at=timestamp,
            previous=previous.get(chapter),
        )
        for chapter, chapter_file in list_chapter_files(novel_dir)
    ]
    _upsert_project(connection, project_root, novel_dir, rows, timestamp)
    connection.execute("DELETE FROM chapters WHERE project_key = ?", (key,))
    if rows:
        columns = [
            "project_key", "chapter_number", "title", "chapter_path", "word_count",
            "chapter_mtime_ns", "passport_path", "passport_mtime_ns", "summary_path",
            "summary_mtime_ns", "pipeline_result", "workflow_stage", "workflow_status",
            "last_completed_stage", "next_action", "writing_gate", "post_write_audit",
            "truth_delta", "truth_sync", "memory_sync", "commit_path", "commit_status",
            "updated_at", "indexed_at",
        ]
        placeholders = ", ".join("?" for _ in columns)
        connection.executemany(
            f"INSERT INTO chapters({', '.join(columns)}) VALUES({placeholders})",
            [tuple(row[column] for column in columns) for row in rows],
        )
    return {"project_key": key, "chapters": len(rows), "updated": len(rows)}


def iter_output_projects(output_root: Path) -> Iterable[Path]:
    if not output_root.is_dir():
        return
    for platform_dir in sorted(output_root.iterdir()):
        if not platform_dir.is_dir() or platform_dir.name.startswith((".", "_")) or platform_dir.name == "archive":
            continue
        for novel_dir in sorted(platform_dir.iterdir()):
            if not novel_dir.is_dir() or novel_dir.name.startswith((".", "_")):
                continue
            if (novel_dir / "novel_state.json").exists() or (novel_dir / "正文").is_dir():
                yield novel_dir


def sync_root_index(project_root: Path, *, output_root: Path | None = None) -> dict[str, Any]:
    """Refresh the active-project read model and remove deleted projects."""
    project_root = project_root.resolve()
    output_root = (output_root or project_root / "novel_output").resolve()
    db_path = index_path(project_root)
    timestamp = now_iso()
    projects = list(iter_output_projects(output_root))
    active_keys = {project_key(project_root, novel_dir) for novel_dir in projects}
    with connect(db_path) as connection:
        ensure_schema(connection)
        for novel_dir in projects:
            sync_project(connection, project_root, novel_dir, indexed_at=timestamp)
        if active_keys:
            placeholders = ", ".join("?" for _ in active_keys)
            connection.execute(
                f"DELETE FROM projects WHERE project_key NOT IN ({placeholders})",
                tuple(sorted(active_keys)),
            )
        else:
            connection.execute("DELETE FROM projects")
        connection.commit()
    return {
        "schema_version": INDEX_SCHEMA_VERSION,
        "path": str(db_path),
        "projects": len(projects),
        "chapters": sum(len(list_chapter_files(path)) for path in projects),
        "indexed_at": timestamp,
    }


def query_projects(db_path: Path) -> list[dict[str, Any]]:
    if not db_path.is_file():
        return []
    with connect(db_path) as connection:
        return [dict(row) for row in connection.execute("SELECT * FROM projects ORDER BY platform, title")]


def query_chapters(db_path: Path, project: str) -> list[dict[str, Any]]:
    if not db_path.is_file():
        return []
    with connect(db_path) as connection:
        return [
            dict(row)
            for row in connection.execute(
                "SELECT * FROM chapters WHERE project_key = ? ORDER BY chapter_number", (project,)
            )
        ]
