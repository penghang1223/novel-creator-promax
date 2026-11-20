"""Per-novel outer workflow state and workspace registry.

The chapter pipeline already isolates state per book. This module closes the
same gap for the outer ``research -> idea -> init -> write -> publish``
workflow: each book gets ``摘要/workflow.json`` and the workspace keeps a
small registry at ``novel_output/_workspace/workflows.json``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .jsonio import load_json, now_iso, save_json
from .paths import rel

WORKFLOW_STAGES = ("research", "idea", "init", "write", "publish")
STAGE_LABELS = {
    "research": "平台调研",
    "idea": "创意生成",
    "init": "立项封存",
    "write": "正文写作",
    "publish": "发布",
}
SCHEMA_VERSION = "1.0"


def novel_workflow_path(novel_dir: Path) -> Path:
    return Path(novel_dir) / "摘要" / "workflow.json"


def legacy_workflow_path(workspace: Path) -> Path:
    return Path(workspace) / "novel_output" / "_workspace" / "workflow.json"


def registry_path(workspace: Path) -> Path:
    return Path(workspace) / "novel_output" / "_workspace" / "workflows.json"


def empty_workflow(book: str = "", platform: str = "", genre: str = "") -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "book": book,
        "platform": platform,
        "genre": genre,
        "stage": "",
        "status": "not_started",
        "research_report": "",
        "idea_card": "",
        "novel_dir": "",
        "history": [],
        "overrides": [],
        "created_at": "",
        "updated_at": "",
    }


def next_stage(stage: str) -> str:
    if stage not in WORKFLOW_STAGES:
        return WORKFLOW_STAGES[0]
    index = WORKFLOW_STAGES.index(stage)
    return WORKFLOW_STAGES[index + 1] if index + 1 < len(WORKFLOW_STAGES) else ""


def load_workflow(
    novel_dir: Path,
    *,
    workspace: Path | None = None,
    migrate: bool = False,
) -> dict[str, Any]:
    novel_dir = Path(novel_dir).resolve()
    payload = load_json(novel_workflow_path(novel_dir), {})
    if not isinstance(payload, dict):
        payload = {}
    if not payload and migrate and workspace is not None:
        payload = migrate_legacy(workspace, novel_dir)
    state = {**empty_workflow(novel_dir.name, novel_dir.parent.name), **payload}
    for key in ("history", "overrides"):
        if not isinstance(state.get(key), list):
            state[key] = []
    if workspace is not None:
        state["novel_dir"] = rel(novel_dir, Path(workspace).resolve())
    return state


def save_workflow(
    novel_dir: Path,
    state: dict[str, Any],
    *,
    workspace: Path | None = None,
) -> dict[str, Any]:
    novel_dir = Path(novel_dir).resolve()
    state = {**empty_workflow(novel_dir.name, novel_dir.parent.name), **state}
    state["schema_version"] = SCHEMA_VERSION
    state["updated_at"] = now_iso()
    if not state.get("created_at"):
        state["created_at"] = state["updated_at"]
    if workspace is not None:
        state["novel_dir"] = rel(novel_dir, Path(workspace).resolve())
        register_book(workspace, novel_dir, state)
    path = novel_workflow_path(novel_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    save_json(path, state)
    return state


def legacy_workflow_for_book(workspace: Path, novel_dir: Path) -> dict[str, Any]:
    legacy = load_json(legacy_workflow_path(workspace), {})
    if not isinstance(legacy, dict) or not legacy.get("novel_dir"):
        return {}
    target = (Path(workspace) / legacy["novel_dir"]).resolve()
    return legacy if target == Path(novel_dir).resolve() else {}


def migrate_legacy(workspace: Path, novel_dir: Path) -> dict[str, Any]:
    """Copy a matching legacy global workflow into this book's workflow.json."""
    workspace = Path(workspace).resolve()
    novel_dir = Path(novel_dir).resolve()
    legacy = legacy_workflow_for_book(workspace, novel_dir)
    if not legacy:
        return {}
    save_workflow(novel_dir, legacy, workspace=workspace)
    backup = legacy_workflow_path(workspace).with_name("workflow.legacy.json")
    if not backup.exists():
        save_json(backup, legacy)
    return legacy


def register_book(workspace: Path, novel_dir: Path, workflow: dict[str, Any]) -> None:
    path = registry_path(workspace)
    payload = load_json(path, {})
    books = payload.get("books") if isinstance(payload, dict) else {}
    if not isinstance(books, dict):
        books = {}
    key = rel(Path(novel_dir).resolve(), Path(workspace).resolve())
    books[key] = {
        "title": workflow.get("book") or Path(novel_dir).name,
        "platform": workflow.get("platform") or Path(novel_dir).parent.name,
        "stage": workflow.get("stage", ""),
        "status": workflow.get("status", ""),
        "updated_at": workflow.get("updated_at", ""),
    }
    save_json(path, {"schema_version": SCHEMA_VERSION, "updated_at": now_iso(), "books": books})


def collect_books(workspace: Path, *, include_legacy: bool = True) -> list[dict[str, Any]]:
    """Return every book with its state and outer workflow (read-only)."""
    workspace = Path(workspace).resolve()
    output = workspace / "novel_output"
    books: list[dict[str, Any]] = []
    seen: set[str] = set()

    for state_path in sorted(output.glob("*/*/novel_state.json")):
        novel_dir = state_path.parent.resolve()
        state = load_json(state_path, {})
        workflow = load_workflow(novel_dir, workspace=workspace)
        if include_legacy and not novel_workflow_path(novel_dir).is_file():
            legacy = legacy_workflow_for_book(workspace, novel_dir)
            if legacy:
                workflow = {**workflow, **legacy, "source": "legacy"}
        books.append(
            {
                "novel_dir": novel_dir,
                "title": str(state.get("title") or novel_dir.name),
                "platform": novel_dir.parent.name,
                "state": state if isinstance(state, dict) else {},
                "workflow": workflow,
                "workflow_source": workflow.get("source", "novel"),
            }
        )
        seen.add(str(novel_dir))

    if include_legacy:
        registry = load_json(registry_path(workspace), {})
        entries = registry.get("books") if isinstance(registry, dict) else {}
        if isinstance(entries, dict):
            for raw, item in sorted(entries.items()):
                novel_dir = (workspace / raw).resolve()
                if str(novel_dir) in seen or not novel_dir.is_dir():
                    continue
                books.append(
                    {
                        "novel_dir": novel_dir,
                        "title": str(item.get("title") or novel_dir.name) if isinstance(item, dict) else novel_dir.name,
                        "platform": novel_dir.parent.name,
                        "state": load_json(novel_dir / "novel_state.json", {}),
                        "workflow": load_workflow(novel_dir, workspace=workspace),
                        "workflow_source": "novel",
                    }
                )
    return books
