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

    _check_state(novel_dir, state, chapter_files, passports, findings)

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
