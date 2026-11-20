#!/usr/bin/env python3
"""Scan active novel projects for unresolved workflow and quality debt."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from novel_creation_promax.core.chapter_commit import commit_path  # noqa: E402
from novel_creation_promax.core.contracts import validate_chapter_contracts  # noqa: E402
from novel_creation_promax.core.jsonio import load_json, now_iso, save_json  # noqa: E402
from novel_creation_promax.core.passport import normalize_status, passport_path  # noqa: E402
from novel_creation_promax.core.paths import list_chapter_files  # noqa: E402
from novel_creation_promax.core.story_index import sync_root_index  # noqa: E402


def iter_projects(output_root: Path) -> Iterable[Path]:
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


def add_debt(items: list[dict[str, Any]], kind: str, severity: str, detail: str, chapter: int | None = None) -> None:
    item: dict[str, Any] = {"kind": kind, "severity": severity, "detail": detail}
    if chapter is not None:
        item["chapter"] = chapter
    items.append(item)


def inspect_project(novel_dir: Path) -> dict[str, Any]:
    state = load_json(novel_dir / "novel_state.json", {})
    state = state if isinstance(state, dict) else {}
    debts: list[dict[str, Any]] = []

    for debt in state.get("override_debt", []):
        if isinstance(debt, dict) and not debt.get("resolved", False):
            add_debt(debts, "override_debt", "high", str(debt.get("reason") or "未提供 override 原因"), debt.get("chapter"))

    lock_dir = novel_dir / "素材" / "runs"
    if lock_dir.is_dir():
        for lock_file in sorted(lock_dir.glob("chapter_*.lock")):
            add_debt(debts, "chapter_lock", "medium", f"锁文件仍存在: {lock_file.name}")

    chapter_summaries: list[dict[str, Any]] = []
    for chapter, chapter_file in list_chapter_files(novel_dir):
        passport_file = passport_path(novel_dir, chapter)
        passport = load_json(passport_file, {})
        if not isinstance(passport, dict):
            add_debt(debts, "passport_missing", "medium", "章节缺少 passport", chapter)
            continue

        workflow = passport.get("workflow", {})
        workflow_status = str(workflow.get("status", "pending")) if isinstance(workflow, dict) else "pending"
        if workflow_status in {"blocked", "fail"}:
            add_debt(debts, "workflow_blocked", "high", str(workflow.get("error") or "章节工作流被阻塞"), chapter)
        elif workflow_status == "running":
            add_debt(debts, "workflow_running", "medium", "章节工作流上次运行未完成", chapter)

        scene_index = passport.get("scene_index", {})
        if isinstance(scene_index, dict) and scene_index.get("enabled") and scene_index.get("status") != "pass":
            add_debt(
                debts,
                "scene_incomplete",
                "medium",
                f"场景 passport 未全部通过: {scene_index.get('passed', 0)}/{scene_index.get('count', 0)}",
                chapter,
            )

        contract_report = validate_chapter_contracts(novel_dir, chapter, passport=passport)
        if contract_report["status"] != "pass":
            add_debt(debts, "contract_invalid", "medium", "; ".join(contract_report["errors"]), chapter)

        pipeline_result = normalize_status(passport.get("pipeline_result"))
        if pipeline_result != "pass":
            add_debt(debts, "pipeline_incomplete", "medium", f"pipeline_result={passport.get('pipeline_result', 'pending')}", chapter)
        elif not commit_path(novel_dir, chapter).exists():
            add_debt(debts, "commit_missing", "high", "章节标记完成但缺少 chapter commit", chapter)

        inputs = passport.get("inputs", {})
        candidate_value = inputs.get("truth_delta_candidates") if isinstance(inputs, dict) else ""
        candidate = Path(candidate_value) if candidate_value else novel_dir / "素材" / f"truth_delta_candidates_ch{chapter:03d}.json"
        if not candidate.is_absolute():
            candidate = novel_dir / candidate
        candidate_payload = load_json(candidate, {})
        if isinstance(candidate_payload, dict) and str(candidate_payload.get("review_status", "")).lower() in {"pending", "needs_review", "待复核"}:
            add_debt(debts, "truth_candidate_review", "medium", f"真相增量待复核: {candidate.name}", chapter)

        chapter_summaries.append(
            {
                "chapter": chapter,
                "file": str(chapter_file),
                "workflow": workflow,
                "pipeline_result": passport.get("pipeline_result", "pending"),
            }
        )

    return {
        "novel_dir": str(novel_dir),
        "title": state.get("title") or novel_dir.name,
        "platform": state.get("platform") or novel_dir.parent.name,
        "debt_count": len(debts),
        "debts": debts,
        "chapters": chapter_summaries,
    }


def build_report(root: Path, novel_dir: Path | None = None) -> dict[str, Any]:
    output_root = root / "novel_output"
    projects = [inspect_project(novel_dir)] if novel_dir else [inspect_project(path) for path in iter_projects(output_root)]
    debts = [debt for project in projects for debt in project["debts"]]
    summary = {
        "projects": len(projects),
        "debts": len(debts),
        "high": sum(1 for debt in debts if debt["severity"] == "high"),
        "medium": sum(1 for debt in debts if debt["severity"] == "medium"),
        "low": sum(1 for debt in debts if debt["severity"] == "low"),
    }
    return {"schema_version": "1.0", "generated_at": now_iso(), "summary": summary, "projects": projects}


def main() -> int:
    parser = argparse.ArgumentParser(description="扫描小说项目质量债务")
    parser.add_argument("--root", default=str(PROJECT_ROOT), help="项目根目录")
    parser.add_argument("--novel-dir", default="", help="只扫描一个小说项目目录")
    parser.add_argument("--output", default="", help="保存 JSON 报告路径")
    parser.add_argument("--json", action="store_true", help="把完整 JSON 打印到 stdout")
    parser.add_argument("--strict", action="store_true", help="存在 high 债务时返回非零")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    novel_dir = Path(args.novel_dir).resolve() if args.novel_dir else None
    report = build_report(root, novel_dir)
    try:
        report["index"] = sync_root_index(root)
    except (OSError, RuntimeError) as exc:
        report["index"] = {"status": "error", "detail": str(exc)}
    if args.output:
        save_json(Path(args.output).resolve(), report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(report["summary"], ensure_ascii=False))
        for project in report["projects"]:
            if project["debt_count"]:
                print(f"[DEBT] {project['novel_dir']}: {project['debt_count']} 项")
    return 1 if args.strict and report["summary"]["high"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
