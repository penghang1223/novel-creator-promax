"""Cross-artifact integrity checks for one novel project.

The chapter pipeline writes the same fact into several places: the prose file,
the chapter passport, the commit ledger and ``novel_state.json``. Each write is
individually guarded, but nothing verified that the four views still agree.
This module provides that missing read-only cross-check.

It never mutates project files. Findings are classified as:

* ``error``   - the views contradict each other in a way that can hide a lost
                chapter or a tampered commit;
* ``warning`` - drift that is common in legacy projects but should be repaired;
* ``info``    - reserved for future aggregate notices.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .chapter_commit import commit_path, load_commit, verify_chapter_commit
from .jsonio import load_json
from .passport import normalize_status
from .paths import count_chinese_chars, infer_chapter_number, list_chapter_files, rel
from .project_state import load_state
from .review_result import review_gate, review_path

REQUIRED_COMMIT_ARTIFACTS = ("chapter", "passport", "audit", "truth_delta")


def _finding(
    code: str,
    severity: str,
    message: str,
    *,
    chapter: int | None = None,
    path: str = "",
    hint: str = "",
) -> dict[str, Any]:
    finding: dict[str, Any] = {
        "code": code,
        "severity": severity,
        "message": message,
        "path": path,
        "hint": hint,
    }
    if chapter is not None:
        finding["chapter"] = chapter
    return finding


def _chapter_passports(novel_dir: Path) -> dict[int, tuple[Path, dict[str, Any]]]:
    passports: dict[int, tuple[Path, dict[str, Any]]] = {}
    summary_dir = novel_dir / "摘要"
    if not summary_dir.is_dir():
        return passports
    for path in sorted(summary_dir.glob("chapter_*_passport.json")):
        chapter = infer_chapter_number(path)
        if chapter is None:
            continue
        payload = load_json(path, {})
        if isinstance(payload, dict):
            passports[chapter] = (path, payload)
    return passports


def _chapter_commits(novel_dir: Path) -> dict[int, Path]:
    commits: dict[int, Path] = {}
    commit_dir = novel_dir / "素材" / "commits"
    if not commit_dir.is_dir():
        return commits
    for path in sorted(commit_dir.glob("chapter_*.commit.json")):
        chapter = infer_chapter_number(path)
        if chapter is not None:
            commits[chapter] = path
    return commits


def _completed_chapters(state: dict[str, Any]) -> set[int]:
    completed: set[int] = set()
    try:
        last = int(state.get("last_completed_chapter", 0) or 0)
    except (TypeError, ValueError):
        last = 0
    completed.update(range(1, last + 1))

    chapters = state.get("chapters", {})
    if isinstance(chapters, dict):
        for key, value in chapters.items():
            if not str(key).isdigit() or not isinstance(value, dict):
                continue
            if normalize_status(value.get("audit_status")) == "pass":
                completed.add(int(key))
            workflow = value.get("workflow", {})
            if isinstance(workflow, dict) and normalize_status(workflow.get("status")) == "pass":
                completed.add(int(key))
    return completed


def _resolve_artifact(novel_dir: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else novel_dir / path


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _check_state(
    novel_dir: Path,
    state: dict[str, Any],
    chapter_files: dict[int, Path],
    passports: dict[int, tuple[Path, dict[str, Any]]],
    findings: list[dict[str, Any]],
) -> None:
    max_file_chapter = max(chapter_files) if chapter_files else 0
    current = _as_int(state.get("current_chapter"))
    last_completed = _as_int(state.get("last_completed_chapter"))

    if current > max_file_chapter:
        findings.append(
            _finding(
                "state_ahead_of_files",
                "error",
                f"novel_state.current_chapter={current}，但正文最大章号只有 {max_file_chapter}",
                chapter=current,
                path="novel_state.json",
                hint="章节文件被删除或回滚；同步 novel_state 或恢复正文",
            )
        )
    if last_completed > max_file_chapter:
        findings.append(
            _finding(
                "state_completed_ahead_of_files",
                "error",
                f"novel_state.last_completed_chapter={last_completed}，但正文最大章号只有 {max_file_chapter}",
                chapter=last_completed,
                path="novel_state.json",
                hint="完成状态早于现存正文，需核对章节是否被误删",
            )
        )

    chapters = state.get("chapters", {})
    if not isinstance(chapters, dict):
        return
    for key, value in sorted(chapters.items(), key=lambda item: str(item[0])):
        if not str(key).isdigit() or not isinstance(value, dict):
            continue
        chapter = int(key)
        passport_ref = value.get("passport")
        if isinstance(passport_ref, str) and passport_ref.strip():
            if not _resolve_artifact(novel_dir, passport_ref).is_file():
                findings.append(
                    _finding(
                        "state_passport_missing",
                        "warning",
                        f"novel_state 第{chapter}章引用的 passport 不存在: {passport_ref}",
                        chapter=chapter,
                        path="novel_state.json",
                        hint="重新同步 novel_state 或补建 passport",
                    )
                )
        elif chapter not in passports and normalize_status(value.get("audit_status")) == "pass":
            findings.append(
                _finding(
                    "state_passport_missing",
                    "warning",
                    f"novel_state 第{chapter}章标记审计通过，但项目中没有 passport",
                    chapter=chapter,
                    path="novel_state.json",
                    hint="补建 passport 或回退该章状态",
                )
            )

        audit_passed = normalize_status(value.get("audit_status")) == "pass"
        entry = passports.get(chapter)
        if audit_passed and entry is not None:
            passport = entry[1]
            workflow = passport.get("workflow", {})
            workflow_status = normalize_status(workflow.get("status")) if isinstance(workflow, dict) else "pending"
            if normalize_status(passport.get("pipeline_result")) != "pass" or workflow_status == "fail":
                findings.append(
                    _finding(
                        "state_passport_conflict",
                        "warning",
                        f"novel_state 第{chapter}章为 pass，但 passport 仍是 "
                        f"{passport.get('pipeline_result', 'pending')}/{workflow.get('status', 'pending') if isinstance(workflow, dict) else 'pending'}",
                        chapter=chapter,
                        path="novel_state.json",
                        hint="以 passport 为准回写 novel_state，或重跑未完成阶段",
                    )
                )


def _check_resume_contract(
    novel_dir: Path,
    state: dict[str, Any],
    passports: dict[int, tuple[Path, dict[str, Any]]],
    findings: list[dict[str, Any]],
) -> None:
    """resume_point, state.chapters[].workflow and passport.workflow must agree."""
    resume = state.get("resume_point")
    if not isinstance(resume, dict):
        return
    chapter = _as_int(resume.get("chapter"))
    if chapter <= 0:
        return

    entry = passports.get(chapter)
    if entry is None:
        max_chapter = max(passports) if passports else 0
        if chapter <= max_chapter:
            findings.append(
                _finding(
                    "resume_passport_missing",
                    "error",
                    f"novel_state.resume_point 指向第{chapter}章，但该章 passport 不存在",
                    chapter=chapter,
                    path="novel_state.json",
                    hint="重跑该章 write_pipeline，或修正 resume_point",
                )
            )
        return

    passport_file, passport = entry
    workflow = passport.get("workflow", {})
    if not isinstance(workflow, dict):
        return

    for key, code in (
        ("stage", "resume_stage_mismatch"),
        ("action", "resume_action_mismatch"),
        ("status", "resume_status_mismatch"),
    ):
        resume_value = str(resume.get(key) or "")
        workflow_value = str(workflow.get("stage" if key == "stage" else "next_action" if key == "action" else "status") or "")
        if not resume_value or not workflow_value or resume_value == workflow_value:
            continue
        severity = "warning" if key == "status" else "error"
        findings.append(
            _finding(
                code,
                severity,
                f"resume_point.{key}={resume_value} 与 passport.workflow 不一致（{workflow_value}）",
                chapter=chapter,
                path=rel(passport_file, novel_dir),
                hint="以 passport.workflow 为准重建 resume_point",
            )
        )

    chapters = state.get("chapters", {})
    chapter_state = chapters.get(f"{chapter:03d}") if isinstance(chapters, dict) else None
    if isinstance(chapter_state, dict) and isinstance(chapter_state.get("workflow"), dict):
        state_workflow = chapter_state["workflow"]
        for key in ("stage", "status", "next_action"):
            left = str(state_workflow.get(key) or "")
            right = str(workflow.get(key) or "")
            if left and right and left != right:
                findings.append(
                    _finding(
                        "state_chapter_workflow_mismatch",
                        "warning",
                        f"novel_state.chapters[{chapter:03d}].workflow.{key} 与 passport 不一致",
                        chapter=chapter,
                        path="novel_state.json",
                        hint="以 passport.workflow 为准同步 novel_state",
                    )
                )
                break


def _check_review(
    novel_dir: Path,
    chapter: int,
    passport: dict[str, Any] | None,
    findings: list[dict[str, Any]],
) -> None:
    """A review must bind the current prose; blockers must not be committed."""
    path = review_path(novel_dir, chapter)
    gate = review_gate(novel_dir, chapter)
    status = str(gate.get("status", "missing"))
    commit = load_commit(novel_dir, chapter)
    committed = isinstance(commit, dict) and commit.get("status") == "accepted"
    pipeline_review = normalize_status((passport or {}).get("pipeline", {}).get("review_result"))

    if status in {"stale", "blocked", "invalid"}:
        findings.append(
            _finding(
                f"review_{status}_committed" if committed else f"review_{status}",
                "error" if committed else "warning",
                f"第{chapter}章结构化审稿状态为 {status}" + ("，但已生成 commit" if committed else ""),
                chapter=chapter,
                path=rel(path, novel_dir),
                hint="重新运行 reviewer 并 save；stale 表示正文在审稿后发生变化",
            )
        )
    elif status == "missing":
        if pipeline_review == "pass":
            findings.append(
                _finding(
                    "review_missing_but_pass",
                    "error",
                    f"第{chapter}章 passport 标记 review_result=pass，但审稿 JSON 不存在",
                    chapter=chapter,
                    path=rel(path, novel_dir),
                    hint="重新审稿，或修正 passport.pipeline.review_result",
                )
            )
        if passport and str(passport.get("quality_mode", "")) == "tribunal" and committed:
            findings.append(
                _finding(
                    "review_missing_tribunal",
                    "error",
                    f"第{chapter}章为 tribunal 模式但缺少结构化审稿",
                    chapter=chapter,
                    path=rel(path, novel_dir),
                    hint="补齐 chapter_NNN_review.json 后重跑 quality / commit",
                )
            )

    if committed and isinstance(commit, dict):
        artifacts = commit.get("artifacts", {})
        snapshot = artifacts.get("review_result") if isinstance(artifacts, dict) else None
        if path.is_file() and (not isinstance(snapshot, dict) or not snapshot.get("exists")):
            findings.append(
                _finding(
                    "review_not_committed",
                    "warning",
                    f"第{chapter}章存在审稿 JSON，但未被 commit 绑定",
                    chapter=chapter,
                    path=rel(path, novel_dir),
                    hint="重跑 post --phase commit，把审稿结果纳入提交指纹",
                )
            )


def _check_rule_stack(
    novel_dir: Path,
    chapter: int,
    chapter_file: Path | None,
    passport: dict[str, Any] | None,
    findings: list[dict[str, Any]],
) -> None:
    """write_ready=false or critical unknown facts must not coexist with prose."""
    path = novel_dir / "摘要" / f"chapter_{chapter:03d}_rule_stack.json"
    pipeline = (passport or {}).get("pipeline", {})
    if not path.is_file():
        if isinstance(pipeline, dict) and normalize_status(pipeline.get("truth_compile")) == "pass":
            findings.append(
                _finding(
                    "rule_stack_missing",
                    "warning",
                    f"第{chapter}章 truth_compile=pass，但 rule_stack 不存在",
                    chapter=chapter,
                    path=rel(path, novel_dir),
                    hint="重跑 pre 阶段生成 rule_stack",
                )
            )
        return

    payload = load_json(path, {})
    if not isinstance(payload, dict):
        findings.append(
            _finding(
                "rule_stack_invalid",
                "error",
                f"第{chapter}章 rule_stack 不是对象",
                chapter=chapter,
                path=rel(path, novel_dir),
                hint="重跑 pre 阶段",
            )
        )
        return

    write_ready = payload.get("write_ready")
    critical = [
        item
        for item in payload.get("unknown_facts", [])
        if isinstance(item, dict) and item.get("critical")
    ]
    if chapter_file is not None and write_ready is False:
        findings.append(
            _finding(
                "rule_stack_not_ready_with_prose",
                "error",
                f"第{chapter}章 rule_stack.write_ready=false，但正文已存在",
                chapter=chapter,
                path=rel(path, novel_dir),
                hint="先补齐 critical 未知事实，或删除正文后重跑 pre",
            )
        )
    if chapter_file is not None and critical:
        findings.append(
            _finding(
                "rule_stack_critical_unknown_with_prose",
                "error",
                f"第{chapter}章存在 {len(critical)} 条 critical 未知事实，但正文已存在",
                chapter=chapter,
                path=rel(path, novel_dir),
                hint="补齐真相文件 open_questions 或把非阻断项标为 critical=false",
            )
        )
    if isinstance(pipeline, dict) and normalize_status(pipeline.get("writing_gate")) == "pass" and write_ready is False:
        findings.append(
            _finding(
                "rule_stack_not_ready_after_gate",
                "error",
                f"第{chapter}章 writing_gate=pass，但 rule_stack.write_ready=false",
                chapter=chapter,
                path=rel(path, novel_dir),
                hint="gate 在未就绪状态下被放行，需重跑 pre / gate",
            )
        )


def _check_commit(
    novel_dir: Path,
    chapter: int,
    passport: dict[str, Any] | None,
    findings: list[dict[str, Any]],
) -> None:
    path = commit_path(novel_dir, chapter)
    pipeline_passed = passport is not None and normalize_status(passport.get("pipeline_result")) == "pass"
    if not path.exists():
        if pipeline_passed:
            findings.append(
                _finding(
                    "commit_missing",
                    "error",
                    f"第{chapter}章 pipeline_result=pass 但缺少 chapter commit",
                    chapter=chapter,
                    path=rel(path, novel_dir),
                    hint="重跑 write_pipeline post --phase commit",
                )
            )
        return

    ok, detail = verify_chapter_commit(novel_dir, chapter)
    if not ok:
        findings.append(
            _finding(
                "commit_invalid",
                "error",
                detail,
                chapter=chapter,
                path=rel(path, novel_dir),
                hint="正文或产物在提交后被改动，需重跑 post 并重新提交",
            )
        )
        return

    payload = load_commit(novel_dir, chapter) or {}
    artifacts = payload.get("artifacts", {})
    if isinstance(artifacts, dict):
        for name in REQUIRED_COMMIT_ARTIFACTS:
            snapshot = artifacts.get(name)
            if not isinstance(snapshot, dict) or not snapshot.get("exists"):
                findings.append(
                    _finding(
                        "commit_artifact_missing",
                        "error",
                        f"第{chapter}章 commit 缺少必需产物 {name}",
                        chapter=chapter,
                        path=rel(path, novel_dir),
                        hint=f"重跑 post 阶段，确保 {name} 被纳入提交指纹",
                    )
                )
    if chapter > 1 and not payload.get("parent_commit"):
        findings.append(
            _finding(
                "commit_parent_gap",
                "warning",
                f"第{chapter}章 commit 没有 parent_commit，提交链断裂",
                chapter=chapter,
                path=rel(path, novel_dir),
                hint="确认上一章 commit 是否缺失；补齐后重跑 commit 阶段",
            )
        )

    if passport is None:
        return

    commit_state = passport.get("commit", {})
    commit_state = commit_state if isinstance(commit_state, dict) else {}
    status = str(commit_state.get("status", "")).strip().lower()
    if status not in {"accepted", "pass", "ok", "synced"}:
        findings.append(
            _finding(
                "passport_commit_unsynced",
                "warning",
                f"chapter commit 已存在，但 passport.commit.status={status or 'empty'}",
                chapter=chapter,
                path=rel(path, novel_dir),
                hint="重跑 commit 阶段，让 passport 指向已接受的 commit",
            )
        )
    elif commit_state.get("id") and commit_state.get("id") != payload.get("commit_id"):
        findings.append(
            _finding(
                "passport_commit_mismatch",
                "warning",
                "passport.commit.id 与实际 commit_id 不一致",
                chapter=chapter,
                path=rel(path, novel_dir),
                hint="以 commit 文件为准重新同步 passport",
            )
        )


def verify_novel_integrity(novel_dir: Path) -> dict[str, Any]:
    novel_dir = Path(novel_dir)
    if not novel_dir.is_dir():
        raise ValueError(f"小说目录不存在: {novel_dir}")
    findings: list[dict[str, Any]] = []
    state = load_state(novel_dir)
    completed = _completed_chapters(state)
    chapter_files = dict(list_chapter_files(novel_dir))
    passports = _chapter_passports(novel_dir)
    commit_chapters = _chapter_commits(novel_dir)

    for chapter in sorted(set(chapter_files) | set(passports) | set(commit_chapters)):
        chapter_file = chapter_files.get(chapter)
        passport_entry = passports.get(chapter)

        if chapter_file is None and passport_entry is None:
            _check_commit(novel_dir, chapter, None, findings)
            findings.append(
                _finding(
                    "commit_orphan",
                    "warning",
                    f"第{chapter}章存在 commit，但找不到正文和 passport",
                    chapter=chapter,
                    path=rel(commit_chapters[chapter], novel_dir),
                    hint="确认章节是否被删除；失效 commit 应随章节一起清理",
                )
            )
            continue

        if chapter_file is not None and passport_entry is None:
            severity = "error" if chapter in completed else "warning"
            findings.append(
                _finding(
                    "passport_missing",
                    severity,
                    f"第{chapter}章正文存在但缺少 passport",
                    chapter=chapter,
                    path=rel(chapter_file, novel_dir),
                    hint="运行 write_pipeline post 或补建对应 chapter passport",
                )
            )
            _check_commit(novel_dir, chapter, None, findings)
            continue

        if passport_entry is None:
            continue

        passport_file, passport = passport_entry
        passport_rel = rel(passport_file, novel_dir)
        declared = str(passport.get("chapter_file", "") or "")
        declared_path = _resolve_artifact(novel_dir, declared) if declared else None

        if chapter_file is None and declared_path is not None and declared_path.is_file():
            # 正文命名不在常规扫描规则内，但 passport 能解析到实际文件。
            chapter_file = declared_path

        if chapter_file is None:
            if declared_path is not None and not declared_path.is_file():
                findings.append(
                    _finding(
                        "chapter_file_missing",
                        "error",
                        f"passport 指向的正文不存在: {declared}",
                        chapter=chapter,
                        path=passport_rel,
                        hint="恢复正文或重新运行 write_pipeline",
                    )
                )
                continue
            severity = "error" if normalize_status(passport.get("pipeline_result")) == "pass" else "warning"
            findings.append(
                _finding(
                    "passport_orphan",
                    severity,
                    f"第{chapter}章 passport 存在但找不到对应正文",
                    chapter=chapter,
                    path=passport_rel,
                    hint="删除失效 passport 或恢复正文文件",
                )
            )
            continue

        if passport.get("chapter") != chapter:
            findings.append(
                _finding(
                    "passport_chapter_mismatch",
                    "error",
                    f"passport 章号 {passport.get('chapter')} 与文件名章号 {chapter} 不一致",
                    chapter=chapter,
                    path=passport_rel,
                    hint="修正 passport.chapter 或文件命名",
                )
            )

        try:
            expected_words = int(passport.get("word_count", 0) or 0)
        except (TypeError, ValueError):
            expected_words = 0
        actual_words = count_chinese_chars(chapter_file.read_text(encoding="utf-8", errors="replace"))
        if expected_words > 0:
            tolerance = max(50, int(expected_words * 0.05))
            if abs(actual_words - expected_words) > tolerance:
                findings.append(
                    _finding(
                        "word_count_drift",
                        "warning",
                        f"passport 记录 {expected_words} 字，正文实际 {actual_words} 字",
                        chapter=chapter,
                        path=rel(chapter_file, novel_dir),
                        hint="正文被改动后需重跑 post 阶段并更新 passport",
                    )
                )

        inputs = passport.get("inputs", {})
        if isinstance(inputs, dict):
            for key, value in sorted(inputs.items()):
                if not isinstance(value, str) or not value.strip():
                    continue
                if not _resolve_artifact(novel_dir, value).is_file():
                    findings.append(
                        _finding(
                            "input_missing",
                            "warning",
                            f"passport.inputs.{key} 声明的产物不存在: {value}",
                            chapter=chapter,
                            path=passport_rel,
                            hint="补齐该阶段产物或清空失效的 inputs 字段",
                        )
                    )

        _check_commit(novel_dir, chapter, passport, findings)
        _check_review(novel_dir, chapter, passport, findings)
        _check_rule_stack(novel_dir, chapter, chapter_file, passport, findings)

    _check_state(novel_dir, state, chapter_files, passports, findings)
    _check_resume_contract(novel_dir, state, passports, findings)

    summary = {
        "chapters_checked": len(set(chapter_files) | set(passports) | set(commit_chapters)),
        "errors": sum(1 for item in findings if item["severity"] == "error"),
        "warnings": sum(1 for item in findings if item["severity"] == "warning"),
    }
    return {
        "novel_dir": str(novel_dir),
        "platform": novel_dir.parent.name,
        "title": str(state.get("title") or novel_dir.name),
        "summary": summary,
        "findings": findings,
    }


def _iter_projects(output_root: Path):
    if not output_root.is_dir():
        return
    for platform_dir in sorted(output_root.iterdir()):
        if not platform_dir.is_dir() or platform_dir.name.startswith((".", "_")) or platform_dir.name == "archive":
            continue
        for novel_dir in sorted(platform_dir.iterdir()):
            if (
                not novel_dir.is_dir()
                or novel_dir.name.startswith((".", "_"))
                or novel_dir.name == "archive"
            ):
                continue
            if (novel_dir / "novel_state.json").exists() or (novel_dir / "正文").is_dir():
                yield novel_dir


def verify_root_integrity(output_root: Path) -> dict[str, Any]:
    output_root = Path(output_root)
    if not output_root.is_dir():
        raise ValueError(f"输出根目录不存在: {output_root}")
    projects = [verify_novel_integrity(novel_dir) for novel_dir in _iter_projects(output_root)]
    summary = {
        "projects": len(projects),
        "chapters_checked": sum(item["summary"]["chapters_checked"] for item in projects),
        "errors": sum(item["summary"]["errors"] for item in projects),
        "warnings": sum(item["summary"]["warnings"] for item in projects),
    }
    return {
        "root": str(output_root),
        "summary": summary,
        "projects": projects,
    }


def report_has_errors(report: dict[str, Any]) -> bool:
    summary = report.get("summary", {}) if isinstance(report, dict) else {}
    return _as_int(summary.get("errors", 0)) > 0
