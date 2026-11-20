"""Markdown dashboards: one per book plus one workspace-wide index."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .integrity import verify_novel_integrity
from .jsonio import load_json
from .passport import normalize_status, passport_path
from .paths import list_chapter_files, rel
from .workflow_state import (
    STAGE_LABELS,
    WORKFLOW_STAGES,
    collect_books,
    legacy_workflow_for_book,
    load_workflow,
    next_stage,
    novel_workflow_path,
)

NOVEL_DASHBOARD = "看板.md"
GLOBAL_DASHBOARD = Path("novel_output") / "_workspace" / "看板.md"
NOVEL_HEADER_RE = re.compile(
    r"\*\*已写 (\d+) 章\*\* \| \*\*阶段: ([^*]+)\*\* \| \*\*健康: (OK|WARN|ERROR)\*\*"
)
GLOBAL_HEADER_RE = re.compile(r"\*\*共 (\d+) 本\*\* \| \*\*(\d+) 本连载中\*\* \| \*\*(\d+) 本完成\*\*")


def novel_dashboard_path(novel_dir: Path) -> Path:
    return Path(novel_dir) / NOVEL_DASHBOARD


def global_dashboard_path(workspace: Path) -> Path:
    return Path(workspace) / GLOBAL_DASHBOARD


def _health(novel_dir: Path) -> tuple[str, dict[str, Any]]:
    try:
        report = verify_novel_integrity(novel_dir)
    except (OSError, ValueError):
        return "ERROR", {"summary": {"errors": 1, "warnings": 0}, "findings": []}
    summary = report.get("summary", {})
    if int(summary.get("errors", 0) or 0) > 0:
        return "ERROR", report
    if int(summary.get("warnings", 0) or 0) > 0:
        return "WARN", report
    return "OK", report


def _stage_index(stage: str) -> int:
    return WORKFLOW_STAGES.index(stage) if stage in WORKFLOW_STAGES else -1


def _workflow_lines(stage: str) -> list[str]:
    current = _stage_index(stage)
    lines = []
    for index, name in enumerate(WORKFLOW_STAGES):
        mark = "x" if index <= current else " "
        marker = " ← 当前" if index == current else ""
        lines.append(f"- [{mark}] {name}（{STAGE_LABELS[name]}）{marker}")
    if current < 0:
        lines[0] = lines[0] + "  ← 未开始"
    return lines


def _chapter_rows(novel_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for chapter, path in sorted(list_chapter_files(novel_dir)):
        passport = load_json(passport_path(novel_dir, chapter), {})
        passport = passport if isinstance(passport, dict) else {}
        pipeline = passport.get("pipeline", {}) if isinstance(passport.get("pipeline"), dict) else {}
        commit = passport.get("commit", {}) if isinstance(passport.get("commit"), dict) else {}
        rows.append(
            {
                "chapter": chapter,
                "file": path,
                "word_count": int(passport.get("word_count", 0) or 0),
                "audit": normalize_status(pipeline.get("post_write_audit")),
                "review": normalize_status(pipeline.get("review_result")),
                "commit": str(commit.get("status", "") or "pending"),
            }
        )
    return rows


def _foreshadowing_open(novel_dir: Path) -> int:
    payload = load_json(novel_dir / "设定" / "真相文件" / "foreshadowing.json", {})
    records = payload.get("records") if isinstance(payload, dict) else []
    if not isinstance(records, list):
        return 0
    open_states = {"open", "active", "open_question", "待回收", "未回收", ""}
    count = 0
    for record in records:
        if not isinstance(record, dict):
            continue
        status = str(record.get("status", "")).strip().lower()
        if status in open_states:
            count += 1
    return count


def _workflow_for(novel_dir: Path, workspace: Path) -> dict[str, Any]:
    workflow = load_workflow(novel_dir, workspace=workspace)
    if not novel_workflow_path(novel_dir).is_file():
        legacy = legacy_workflow_for_book(workspace, novel_dir)
        if legacy:
            workflow = {**workflow, **legacy, "source": "legacy"}
    return workflow


def render_novel_dashboard(novel_dir: Path, workspace: Path) -> str:
    novel_dir = Path(novel_dir).resolve()
    workspace = Path(workspace).resolve()
    state = load_json(novel_dir / "novel_state.json", {})
    state = state if isinstance(state, dict) else {}
    workbook = _workflow_for(novel_dir, workspace)
    stage = str(workbook.get("stage", "") or "")
    health, report = _health(novel_dir)
    title = str(state.get("title") or novel_dir.name)
    platform = str(state.get("platform") or novel_dir.parent.name)
    genre = str(state.get("genre") or _workflow_genre(workbook))
    pack_id = str(state.get("pack_id") or "")
    current = int(state.get("current_chapter", 0) or 0)
    last_completed = int(state.get("last_completed_chapter", 0) or 0)

    lines = [
        f"# {title} · 看板",
        "",
        f"> 平台：{platform} · 题材：{genre or '-'}" + (f" · 能力包：{pack_id}" if pack_id else ""),
        f"> 项目：{rel(novel_dir, workspace)}",
        "",
        f"**已写 {current} 章** | **阶段: {stage or '未开始'}** | **健康: {health}**",
        "",
        "## 外层工作流",
        "",
        *_workflow_lines(stage),
        "",
    ]

    resume = state.get("resume_point", {})
    resume = resume if isinstance(resume, dict) else {}
    lines.extend(
        [
            "## 当前章节",
            "",
            f"- 当前章：第 {current} 章（已完成 {last_completed} 章）",
            f"- 连载下一步：{resume.get('action') or 'pre'}",
        ]
    )
    if resume.get("hint"):
        lines.append(f"- 提示：{resume['hint']}")
    lines.append("")

    rows = _chapter_rows(novel_dir)
    lines.extend(["## 最近章节", "", "| 章 | 字数 | 审计 | 审稿 | commit |", "|---:|---:|---|---|---|"])
    if rows:
        for row in rows[-5:]:
            lines.append(
                f"| {row['chapter']} | {row['word_count']} | {row['audit']} | "
                f"{row['review']} | {row['commit']} |"
            )
    else:
        lines.append("| - | - | - | - | 尚无正文 |")
    lines.extend(
        [
            "",
            "## 伏笔 / 债务",
            "",
            f"- 未回收伏笔：{_foreshadowing_open(novel_dir)} 条（来自 设定/真相文件/foreshadowing.json）",
            "",
            "## 健康",
            "",
        ]
    )
    summary = report.get("summary", {})
    lines.append(
        f"- 一致性：{int(summary.get('errors', 0) or 0)} error / "
        f"{int(summary.get('warnings', 0) or 0)} warning"
    )
    findings = report.get("findings", [])
    for finding in [item for item in findings if item.get("severity") == "error"][:3]:
        chapter = f" 第{finding['chapter']}章" if finding.get("chapter") is not None else ""
        lines.append(f"- ❌ `{finding.get('code', '')}`{chapter}: {finding.get('message', '')}")
    lines.append("")
    updated = str(state.get("updated_at") or workbook.get("updated_at") or "-")
    lines.append(f"_更新于 {updated}_")
    lines.append("")
    return "\n".join(lines)


def _workflow_genre(workflow: dict[str, Any]) -> str:
    return str(workflow.get("genre", "") or "")


def render_global_dashboard(workspace: Path) -> str:
    workspace = Path(workspace).resolve()
    books = collect_books(workspace)
    total = len(books)
    completed = sum(1 for book in books if str(book["workflow"].get("stage", "")) == "publish")
    active = total - completed
    lines = [
        "# 小说总看板",
        "",
        f"**共 {total} 本** | **{active} 本连载中** | **{completed} 本完成**",
        "",
        "| 书名 | 平台 | 当前章 | 外层阶段 | 外层下一阶段 | 健康 | 更新时间 |",
        "|---|---|---:|---|---|---|---|",
    ]
    if not books:
        lines.append("| - | - | - | - | - | - | 尚无项目 |")
    for book in books:
        novel_dir = book["novel_dir"]
        state = book["state"]
        workflow = book["workflow"]
        health, _report = _health(novel_dir)
        stage = str(workflow.get("stage", "") or "")
        stage_next = next_stage(stage) if stage else "research"
        lines.append(
            f"| {book['title']} | {book['platform']} | "
            f"{int(state.get('current_chapter', 0) or 0)} | "
            f"{stage or '未开始'} | {stage_next or '完成'} | "
            f"{health} | {str(workflow.get('updated_at') or '-')[:19]} |"
        )
    updated = max((str(book["workflow"].get("updated_at") or "") for book in books), default="")
    lines.extend(["", f"_更新于 {updated or '-'}_", ""])
    return "\n".join(lines)


def render_all(workspace: Path, novel_dir: Path | None = None) -> dict[Path, str]:
    workspace = Path(workspace).resolve()
    rendered: dict[Path, str] = {}
    targets = [Path(novel_dir).resolve()] if novel_dir else [book["novel_dir"] for book in collect_books(workspace)]
    for target in targets:
        if target.is_dir():
            rendered[novel_dashboard_path(target)] = render_novel_dashboard(target, workspace)
    rendered[global_dashboard_path(workspace)] = render_global_dashboard(workspace)
    return rendered


def write_dashboards(workspace: Path, novel_dir: Path | None = None) -> list[Path]:
    written = []
    for path, text in render_all(workspace, novel_dir).items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        written.append(path)
    return written


def check_dashboards(workspace: Path, novel_dir: Path | None = None) -> list[str]:
    problems = []
    for path, text in render_all(workspace, novel_dir).items():
        try:
            current = path.read_text(encoding="utf-8")
        except OSError:
            problems.append(f"缺失看板: {path}")
            continue
        if current != text:
            problems.append(f"看板漂移: {path}")
    return problems
