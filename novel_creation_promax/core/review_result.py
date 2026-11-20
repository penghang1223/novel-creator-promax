"""Structured single-chapter review results.

The reviewer subagent returns JSON only. This module is the single source of
truth for the schema, normalization, validation and gate calculation, so the
write pipeline never depends on free-form review prose.

The review is bound to an exact chapter revision via ``target.sha256`` and
every blocking/major issue must quote the source text through ``source_refs``.
A review produced against an older draft therefore cannot silently pass the
gate: it is reported as ``stale``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .chapter_commit import sha256_file
from .jsonio import load_json, now_iso, read_text, save_json
from .paths import count_chinese_chars, find_chapter_file, rel
from .review_basis import (
    expected_versions_from_basis,
    review_basis_gate,
)
from .revision_control import current_revision

REVIEW_SCHEMA_VERSION = "1.0"
REVIEW_CONTRACT = "chapter_review"

REVIEW_DIMENSIONS = (
    "dialogue",
    "coolpoint",
    "structure",
    "anti_ai",
    "reading_power",
)
DIMENSION_LABELS: dict[str, str] = {
    "dialogue": "对话质感",
    "coolpoint": "爽点节奏",
    "structure": "章节结构",
    "anti_ai": "去AI化",
    "reading_power": "追读力",
    "cross": "跨维度",
}

REVIEW_MODES = ("single", "batch")
SEVERITIES = ("blocker", "major", "minor")
SEVERITY_RANK = {"blocker": 0, "major": 1, "minor": 2}
ASSESSMENTS = ("issue", "resolved", "unavailable", "observation")
GRADES = ("S", "A", "B", "C", "D")
STATUSES = ("pass", "blocked")
GATE_STATUSES = ("missing", "pass", "blocked", "invalid", "stale")

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class DuplicateJsonKeyError(ValueError):
    """Raised when a review JSON object repeats a field name."""


class _ObjectPairs(list):
    """Keep object pairs so duplicate keys are visible before dict conversion."""


def _walk_json_paths(value: Any, path: str) -> None:
    if isinstance(value, _ObjectPairs):
        seen: set[str] = set()
        for key, child in value:
            child_path = f"{path}[{json.dumps(key, ensure_ascii=False)}]"
            if key in seen:
                raise DuplicateJsonKeyError(f"review JSON 存在重复字段: {child_path}")
            seen.add(key)
            _walk_json_paths(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _walk_json_paths(child, f"{path}[{index}]")


def reject_duplicate_json_keys(raw: str) -> None:
    """Reject duplicate object keys instead of silently keeping the last one."""
    value = json.loads(raw, object_pairs_hook=_ObjectPairs)
    _walk_json_paths(value, "$")


def parse_review_json(raw: str) -> dict[str, Any]:
    reject_duplicate_json_keys(raw)
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("review JSON 必须是对象")
    return payload


def review_path(novel_dir: Path, chapter: int) -> Path:
    return novel_dir / "摘要" / f"chapter_{chapter:03d}_review.json"


def chapter_target(novel_dir: Path, chapter: int) -> dict[str, Any] | None:
    """Return the exact chapter revision a review must bind to."""
    chapter_file = find_chapter_file(novel_dir, chapter)
    if chapter_file is None or not chapter_file.is_file():
        return None
    text = read_text(chapter_file)
    digest = sha256_file(chapter_file)
    tracked = current_revision(novel_dir, chapter)
    tracked_matches = tracked is not None and tracked.get("content_hash") == digest
    if tracked_matches:
        revision_state = "tracked"
    elif tracked is not None:
        revision_state = "outdated"
    else:
        revision_state = "untracked"
    return {
        "chapter_file": rel(chapter_file, novel_dir),
        "sha256": digest,
        "word_count": count_chinese_chars(text),
        "revision_id": tracked.get("revision_id", "") if tracked_matches else "",
        "revision_version": tracked.get("version") if tracked_matches else None,
        "revision_state": revision_state,
    }


def _normalize_target(value: Any) -> dict[str, Any]:
    payload = value if isinstance(value, dict) else {}
    word_count = payload.get("word_count")
    try:
        normalized_word_count = int(word_count) if word_count is not None else None
    except (TypeError, ValueError):
        normalized_word_count = None
    revision_version = payload.get("revision_version")
    try:
        normalized_revision_version = int(revision_version) if revision_version is not None else None
    except (TypeError, ValueError):
        normalized_revision_version = None
    return {
        "chapter_file": str(payload.get("chapter_file") or "").strip(),
        "sha256": str(payload.get("sha256") or "").strip().lower(),
        "word_count": normalized_word_count,
        "revision_id": str(payload.get("revision_id") or "").strip(),
        "revision_version": normalized_revision_version,
    }


def init_review_result(
    chapter: int,
    *,
    mode: str = "single",
    target: dict[str, Any] | None = None,
    basis: dict[str, Any] | None = None,
    expected_versions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a deliberately blocked template so an empty file can never pass."""
    normalized_basis = basis if isinstance(basis, dict) else {}
    return {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "chapter": chapter,
        "mode": mode if mode in REVIEW_MODES else "single",
        "target": _normalize_target(target),
        "basis": normalized_basis,
        "expected_versions": (
            {str(key): str(value) for key, value in expected_versions.items()}
            if isinstance(expected_versions, dict)
            else expected_versions_from_basis(normalized_basis)
        ),
        "dimensions": {
            name: {"score": None, "summary": "", "issues": []}
            for name in REVIEW_DIMENSIONS
        },
        "issues": [
            {
                "id": "R-001",
                "severity": "blocker",
                "assessment": "unavailable",
                "dimension": "cross",
                "location": "",
                "evidence": "审稿尚未完成",
                "impact": "无法判断本章是否满足交付标准",
                "repair": "按 reviewer 契约补齐五维评分、目标哈希和原文引用后重新运行",
                "source_refs": [],
            }
        ],
        "blocking_count": 1,
        "status": "blocked",
        "grade": "",
        "summary": "审稿模板，尚未完成",
        "generated_at": now_iso(),
    }


def _coerce_score(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        score = int(value)
    except (TypeError, ValueError):
        return None
    return max(0, min(10, score))


def _coerce_line(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 1 else None


def _coerce_offset(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _normalize_dimension(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"score": None, "summary": "", "issues": []}
    issues = value.get("issues")
    return {
        "score": _coerce_score(value.get("score")),
        "summary": _text(value.get("summary")),
        "issues": [str(item) for item in issues if str(item).strip()] if isinstance(issues, list) else [],
    }


def _normalize_source_ref(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    quote = _text(raw.get("quote"))
    if not quote:
        return None
    return {
        "quote": quote,
        "start": _coerce_offset(raw.get("start")),
        "end": _coerce_offset(raw.get("end")),
        "start_line": _coerce_line(raw.get("start_line")),
        "end_line": _coerce_line(raw.get("end_line")),
    }


def _normalize_issue(raw: Any, index: int) -> dict[str, Any]:
    payload = raw if isinstance(raw, dict) else {}
    severity = _text(payload.get("severity")).lower() or "minor"
    assessment = _text(payload.get("assessment")).lower() or "issue"
    dimension = _text(payload.get("dimension")) or "cross"
    raw_refs = payload.get("source_refs")
    source_refs = [
        ref
        for ref in (
            _normalize_source_ref(item)
            for item in (raw_refs if isinstance(raw_refs, list) else [])
        )
        if ref is not None
    ]
    return {
        "id": _text(payload.get("id")) or f"R-{index:03d}",
        "severity": severity,
        "assessment": assessment,
        "code": _text(payload.get("code")).upper(),
        "dimension": dimension,
        "location": _text(payload.get("location")),
        "evidence": _text(payload.get("evidence")),
        "impact": _text(payload.get("impact")),
        "repair": _text(payload.get("repair")),
        "source_refs": source_refs,
    }


def _derive_grade(dimensions: dict[str, dict[str, Any]]) -> str:
    scores = [
        item["score"]
        for item in dimensions.values()
        if isinstance(item.get("score"), int) and not isinstance(item.get("score"), bool)
    ]
    if not scores:
        return ""
    average = sum(scores) / len(scores)
    if average >= 9:
        return "S"
    if average >= 8:
        return "A"
    if average >= 7:
        return "B"
    if average >= 6:
        return "C"
    return "D"


def normalize_review_result(payload: Any, *, chapter: int | None = None) -> dict[str, Any]:
    """Return a canonical review result and derive status from blocking issues."""
    source = payload if isinstance(payload, dict) else {}
    source_dimensions = source.get("dimensions")
    dimensions = {
        name: _normalize_dimension(
            source_dimensions.get(name) if isinstance(source_dimensions, dict) else None
        )
        for name in REVIEW_DIMENSIONS
    }

    raw_issues = source.get("issues")
    issues = [
        _normalize_issue(item, index)
        for index, item in enumerate(raw_issues if isinstance(raw_issues, list) else [], 1)
    ]
    issues.sort(key=lambda item: (SEVERITY_RANK.get(item["severity"], 9), item["id"]))

    blocking_count = sum(1 for item in issues if item["severity"] == "blocker")
    status = "blocked" if blocking_count else "pass"
    grade = _text(source.get("grade")).upper()
    if grade not in GRADES:
        grade = _derive_grade(dimensions)

    mode = _text(source.get("mode")).lower()
    raw_basis = source.get("basis")
    raw_versions = source.get("expected_versions")
    return {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "chapter": chapter if chapter is not None else source.get("chapter", 0),
        "mode": mode if mode in REVIEW_MODES else "single",
        "target": _normalize_target(source.get("target")),
        "basis": dict(raw_basis) if isinstance(raw_basis, dict) else {},
        "expected_versions": (
            {str(key): str(value) for key, value in raw_versions.items()}
            if isinstance(raw_versions, dict)
            else {}
        ),
        "dimensions": dimensions,
        "issues": issues,
        "blocking_count": blocking_count,
        "status": status,
        "grade": grade,
        "summary": _text(source.get("summary")),
        "generated_at": _text(source.get("generated_at")) or now_iso(),
    }


def validate_review_result(payload: Any, *, chapter: int | None = None) -> dict[str, Any]:
    """Validate a review result's shape without reading the chapter file.

    Freshness (target hash) and source-quote matching need the chapter text and
    are therefore enforced by :func:`review_gate`.
    """
    report: dict[str, Any] = {
        "contract": REVIEW_CONTRACT,
        "status": "pass",
        "errors": [],
        "warnings": [],
    }
    if not isinstance(payload, dict):
        report["status"] = "fail"
        report["errors"].append("review result 必须是 JSON 对象")
        return report

    expected_chapter = chapter
    actual_chapter = payload.get("chapter")
    if expected_chapter is not None:
        if actual_chapter in {None, ""}:
            report["errors"].append("缺少 chapter")
        else:
            try:
                if int(actual_chapter) != expected_chapter:
                    report["errors"].append(
                        f"章号不匹配: expected={expected_chapter}, actual={actual_chapter}"
                    )
            except (TypeError, ValueError):
                report["errors"].append(f"chapter 不是整数: {actual_chapter}")

    mode = _text(payload.get("mode")) or "single"
    if mode not in REVIEW_MODES:
        report["warnings"].append(f"未知 mode: {mode}，按 single 处理")

    target = payload.get("target")
    if not isinstance(target, dict):
        report["errors"].append("缺少 target：审稿必须绑定正文 revision")
    else:
        digest = _text(target.get("sha256")).lower()
        if not digest:
            report["errors"].append("target.sha256 不能为空")
        elif not _SHA256_RE.match(digest):
            report["errors"].append("target.sha256 必须是 64 位十六进制 SHA-256")
        chapter_file = _text(target.get("chapter_file"))
        if chapter_file and (
            chapter_file.startswith(("/", "\\"))
            or re.match(r"^[a-zA-Z]:[\\/]", chapter_file)
            or ".." in Path(chapter_file).parts
        ):
            report["errors"].append(f"target.chapter_file 必须是项目内相对路径: {chapter_file}")
        revision_id = _text(target.get("revision_id"))
        revision_version = target.get("revision_version")
        if revision_id:
            if not re.match(r"^rev_[A-Za-z0-9_-]{6,120}$", revision_id):
                report["errors"].append(f"target.revision_id 格式无效: {revision_id}")
            if (
                isinstance(revision_version, bool)
                or not isinstance(revision_version, int)
                or revision_version < 1
            ):
                report["errors"].append("target.revision_id 存在时 revision_version 必须是正整数")
        elif revision_version is not None:
            report["errors"].append("target.revision_version 必须与 revision_id 一起提供")
        else:
            report["warnings"].append(
                "target.revision_id 为空：审稿未绑定 revision，建议使用 target --ensure-revision"
            )

    basis = payload.get("basis")
    expected_versions = payload.get("expected_versions")
    if basis is not None and not isinstance(basis, dict):
        report["errors"].append("basis 必须是对象")
        basis = None
    if isinstance(basis, dict) and basis:
        for key in ("workflow", "step", "schema_id"):
            if not _text(basis.get(key)):
                report["errors"].append(f"basis.{key} 不能为空")
        schema_version = basis.get("schema_version")
        if isinstance(schema_version, bool) or not isinstance(schema_version, int) or schema_version < 1:
            report["errors"].append("basis.schema_version 必须是正整数")
        prompt_version = basis.get("prompt_version")
        if prompt_version is not None and (
            isinstance(prompt_version, bool)
            or not isinstance(prompt_version, int)
            or prompt_version < 1
        ):
            report["errors"].append("basis.prompt_version 必须是正整数")
        fingerprint = _text(basis.get("input_fingerprint"))
        if not fingerprint:
            report["errors"].append("basis.input_fingerprint 不能为空")
        elif not _SHA256_RE.match(fingerprint):
            report["errors"].append("basis.input_fingerprint 必须是 64 位十六进制 SHA-256")
        source_refs = basis.get("source_refs")
        if not isinstance(source_refs, list):
            report["errors"].append("basis.source_refs 必须是数组")
            source_refs = []
        for ref_index, ref in enumerate(source_refs, 1):
            if not isinstance(ref, dict):
                report["errors"].append(f"basis.source_refs#{ref_index} 必须是对象")
                continue
            if not _text(ref.get("resource_type")):
                report["errors"].append(f"basis.source_refs#{ref_index}.resource_type 不能为空")
            if not _text(ref.get("id")):
                report["errors"].append(f"basis.source_refs#{ref_index}.id 不能为空")
            digest = _text(ref.get("sha256"))
            if digest and not _SHA256_RE.match(digest):
                report["errors"].append(f"basis.source_refs#{ref_index}.sha256 必须是 64 位十六进制")
    if expected_versions is not None and not isinstance(expected_versions, dict):
        report["errors"].append("expected_versions 必须是对象")
    elif isinstance(expected_versions, dict):
        for key, value in expected_versions.items():
            if not str(key).strip():
                report["errors"].append("expected_versions 的 key 不能为空")
            if not isinstance(value, str):
                report["errors"].append(f"expected_versions[{key}] 必须是字符串 SHA-256")
            elif value and not _SHA256_RE.match(value):
                report["errors"].append(f"expected_versions[{key}] 必须是 64 位十六进制或空字符串")
    if not basis and not expected_versions:
        report["warnings"].append(
            "未绑定 basis；建议 target --with-basis 后重新审稿"
        )

    dimensions = payload.get("dimensions")
    if not isinstance(dimensions, dict):
        report["errors"].append("dimensions 必须是对象")
        dimensions = {}
    missing_dimensions = [name for name in REVIEW_DIMENSIONS if name not in dimensions]
    if missing_dimensions:
        report["errors"].append(f"缺少审查维度: {', '.join(missing_dimensions)}")

    for name in REVIEW_DIMENSIONS:
        item = dimensions.get(name)
        if item is None:
            continue
        if not isinstance(item, dict):
            report["errors"].append(f"dimensions.{name} 必须是对象")
            continue
        score = item.get("score")
        if score is not None and (
            isinstance(score, bool) or not isinstance(score, int) or score < 0 or score > 10
        ):
            report["errors"].append(f"dimensions.{name}.score 必须是 0-10 的整数或 null")
        if not _text(item.get("summary")):
            report["warnings"].append(f"dimensions.{name}.summary 为空")

    issues = payload.get("issues")
    if not isinstance(issues, list):
        report["errors"].append("issues 必须是数组")
        issues = []

    blocking_count = 0
    seen_ids: set[str] = set()
    for index, item in enumerate(issues, 1):
        if not isinstance(item, dict):
            report["errors"].append(f"issues#{index} 必须是对象")
            continue
        issue_id = _text(item.get("id")) or f"R-{index:03d}"
        if issue_id in seen_ids:
            report["errors"].append(f"issue id 重复: {issue_id}")
        seen_ids.add(issue_id)

        severity = _text(item.get("severity")).lower()
        if severity not in SEVERITIES:
            report["errors"].append(f"issues#{index} severity 必须是 blocker/major/minor")
        if severity == "blocker":
            blocking_count += 1

        assessment = _text(item.get("assessment")).lower() or "issue"
        if assessment not in ASSESSMENTS:
            report["errors"].append(
                f"issues#{index} assessment 必须是 issue/resolved/unavailable/observation"
            )

        dimension = _text(item.get("dimension")) or "cross"
        if dimension not in DIMENSION_LABELS:
            report["errors"].append(f"issues#{index} 未知 dimension: {dimension}")
        code = _text(item.get("code")).upper()
        if code and not re.match(r"^[A-Z][A-Z0-9_]{2,63}$", code):
            report["errors"].append(f"issues#{index}.code 格式无效: {code}")
        if not _text(item.get("evidence")):
            report["errors"].append(f"issues#{index} 缺少 evidence")
        if severity == "blocker" and not _text(item.get("repair")):
            report["errors"].append(f"issues#{index} 是 blocker，必须给出 repair")

        refs = item.get("source_refs")
        if refs is None:
            refs = []
        if not isinstance(refs, list):
            report["errors"].append(f"issues#{index} source_refs 必须是数组")
            refs = []
        if severity in {"blocker", "major"} and assessment != "unavailable" and not refs:
            report["errors"].append(
                f"issues#{index} 是 {severity}，必须提供至少一条 source_refs 原文引用"
            )
        for ref_index, ref in enumerate(refs, 1):
            if not isinstance(ref, dict):
                report["errors"].append(f"issues#{index}.source_refs#{ref_index} 必须是对象")
                continue
            quote = _text(ref.get("quote"))
            if not quote:
                report["errors"].append(
                    f"issues#{index}.source_refs#{ref_index}.quote 不能为空"
                )
                continue
            if len(quote) > 2000:
                report["warnings"].append(
                    f"issues#{index}.source_refs#{ref_index}.quote 超过 2000 字，建议截取关键句"
                )
            start = ref.get("start_line")
            end = ref.get("end_line")
            if (start is None) != (end is None):
                report["errors"].append(
                    f"issues#{index}.source_refs#{ref_index} start_line/end_line 必须同时提供"
                )
            elif start is not None:
                if (
                    isinstance(start, bool) or not isinstance(start, int) or start < 1
                    or isinstance(end, bool) or not isinstance(end, int) or end < start
                ):
                    report["errors"].append(
                        f"issues#{index}.source_refs#{ref_index} 行号范围无效"
                    )
            offset_start = ref.get("start")
            offset_end = ref.get("end")
            if offset_start is not None and (
                isinstance(offset_start, bool) or not isinstance(offset_start, int) or offset_start < 0
            ):
                report["errors"].append(
                    f"issues#{index}.source_refs#{ref_index}.start 必须是 >=0 的整数"
                )
            if offset_end is not None:
                if offset_start is None:
                    report["errors"].append(
                        f"issues#{index}.source_refs#{ref_index}.end 必须与 start 一起提供"
                    )
                elif (
                    isinstance(offset_end, bool) or not isinstance(offset_end, int)
                    or offset_end < offset_start
                ):
                    report["errors"].append(
                        f"issues#{index}.source_refs#{ref_index} 字符范围无效"
                    )

    declared_blocking = payload.get("blocking_count")
    if declared_blocking is not None and declared_blocking != blocking_count:
        report["errors"].append(
            f"blocking_count 与 issues 不一致: declared={declared_blocking}, actual={blocking_count}"
        )
    expected_status = "blocked" if blocking_count else "pass"
    declared_status = _text(payload.get("status")).lower()
    if declared_status and declared_status != expected_status:
        report["errors"].append(
            f"status 与 blocking_count 不一致: declared={declared_status}, expected={expected_status}"
        )
    if not declared_status:
        report["errors"].append("缺少 status")

    grade = _text(payload.get("grade")).upper()
    if grade and grade not in GRADES:
        report["errors"].append(f"未知 grade: {grade}")

    if not _text(payload.get("summary")):
        report["warnings"].append("summary 为空")

    report["status"] = "fail" if report["errors"] else "pass"
    return report


def load_review_result_checked(
    novel_dir: Path,
    chapter: int,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Load a review JSON, rejecting duplicate fields and malformed content."""
    path = review_path(novel_dir, chapter)
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None, []
    except OSError as exc:
        return None, [f"读取审稿 JSON 失败: {exc}"]
    try:
        return parse_review_json(raw), []
    except (DuplicateJsonKeyError, json.JSONDecodeError, ValueError) as exc:
        return None, [str(exc)]


def load_review_result(novel_dir: Path, chapter: int) -> dict[str, Any] | None:
    payload, _errors = load_review_result_checked(novel_dir, chapter)
    return payload


def save_review_result(
    novel_dir: Path,
    chapter: int,
    payload: Any,
    *,
    bind_target: bool = False,
) -> Path:
    source = dict(payload) if isinstance(payload, dict) else {}
    if bind_target:
        target = chapter_target(novel_dir, chapter)
        if target is None:
            raise ValueError(f"第{chapter}章正文不存在，无法绑定审稿目标")
        source["target"] = target
    normalized = normalize_review_result(source, chapter=chapter)
    path = review_path(novel_dir, chapter)
    save_json(path, normalized)
    return path


def _quote_matches(
    text: str,
    quote: str,
    start: int | None,
    end: int | None,
    start_line: int | None,
    end_line: int | None,
) -> bool:
    normalized_text = text.replace("\r\n", "\n")
    normalized_quote = quote.replace("\r\n", "\n")
    if not normalized_quote.strip():
        return False
    if start is not None:
        resolved_end = end if end is not None else start + len(normalized_quote)
        if start < 0 or resolved_end < start or resolved_end > len(normalized_text):
            return False
        return normalized_text[start:resolved_end] == normalized_quote
    if start_line is not None and end_line is not None:
        lines = normalized_text.splitlines()
        if start_line < 1 or end_line < start_line or end_line > len(lines):
            return False
        scoped = "\n".join(lines[start_line - 1:end_line])
        return normalized_quote in scoped
    return normalized_quote.strip() in normalized_text


def _quote_errors(
    issues: list[dict[str, Any]],
    chapter_text: str,
) -> list[str]:
    errors: list[str] = []
    for issue in issues:
        for index, ref in enumerate(issue.get("source_refs") or [], 1):
            if not _quote_matches(
                chapter_text,
                ref["quote"],
                ref.get("start"),
                ref.get("end"),
                ref.get("start_line"),
                ref.get("end_line"),
            ):
                preview = ref["quote"][:60].replace("\n", " ")
                errors.append(
                    f"{issue['id']}.source_refs#{index} 引文未在正文中找到: {preview}"
                )
    return errors


def review_gate(novel_dir: Path, chapter: int) -> dict[str, Any]:
    """Compute the commit gate contribution of the chapter review result.

    ``missing`` means no review was produced. ``stale`` means the review was
    produced against a different chapter revision. ``blocked`` and ``invalid``
    must always block commit.
    """
    path = review_path(novel_dir, chapter)
    payload, load_errors = load_review_result_checked(novel_dir, chapter)
    if load_errors:
        report = {
            "contract": REVIEW_CONTRACT,
            "status": "fail",
            "errors": load_errors,
            "warnings": [],
        }
        return {
            "status": "invalid",
            "path": path,
            "blocking_count": 0,
            "issues": [],
            "target": {},
            "report": report,
        }
    if payload is None:
        return {
            "status": "missing",
            "path": path,
            "blocking_count": 0,
            "issues": [],
            "target": {},
            "report": {"contract": REVIEW_CONTRACT, "status": "pass", "errors": [], "warnings": []},
        }

    report = validate_review_result(payload, chapter=chapter)
    normalized = normalize_review_result(payload, chapter=chapter)
    result = {
        "status": "invalid",
        "path": path,
        "blocking_count": normalized["blocking_count"],
        "issues": normalized["issues"],
        "target": normalized["target"],
        "basis": normalized.get("basis", {}),
        "review": normalized,
        "report": report,
    }
    if report["status"] != "pass":
        return result

    current = chapter_target(novel_dir, chapter)
    if current is None:
        report["status"] = "fail"
        report["errors"].append("章节正文不存在，无法验证审稿目标")
        result["status"] = "stale"
        result["report"] = report
        return result

    target = normalized["target"]
    if target["sha256"] != current["sha256"]:
        report["status"] = "fail"
        report["errors"].append(
            "审稿目标已过期：正文 SHA-256 与审稿记录不一致，请重新审稿"
        )
        report["errors"].append(f"expected={current['sha256']}")
        report["errors"].append(f"actual={target['sha256']}")
        result["status"] = "stale"
        result["report"] = report
        return result

    tracked = current_revision(novel_dir, chapter)
    target_revision_id = str(target.get("revision_id") or "")
    if target_revision_id:
        if tracked is None:
            report["status"] = "fail"
            report["errors"].append(
                "审稿绑定了 revision，但当前章节没有 revision 记录，请重新运行 target --ensure-revision"
            )
            result["status"] = "stale"
            result["report"] = report
            return result
        if tracked.get("revision_id") != target_revision_id:
            report["status"] = "fail"
            report["errors"].append(
                f"审稿 revision 已不是当前版本: target={target_revision_id}, current={tracked.get('revision_id')}"
            )
            result["status"] = "stale"
            result["report"] = report
            return result
        if tracked.get("content_hash") != target.get("sha256"):
            report["status"] = "fail"
            report["errors"].append("当前 revision 的 content_hash 与审稿目标不一致")
            result["status"] = "stale"
            result["report"] = report
            return result
    else:
        report["warnings"].append(
            "审稿未绑定 revision_id；建议使用 target --ensure-revision 后重新审稿"
        )
    if tracked is not None and tracked.get("content_hash") != current["sha256"]:
        report["warnings"].append(
            "当前 revision 记录与正文不一致；建议重新运行 target --ensure-revision"
        )

    basis_result = review_basis_gate(novel_dir, chapter, payload)
    if basis_result["status"] in {"invalid", "stale"}:
        report["status"] = "fail"
        report["errors"].extend(basis_result["errors"])
        result["status"] = "stale"
        result["report"] = report
        return result
    report["warnings"].extend(basis_result["warnings"])

    chapter_file = find_chapter_file(novel_dir, chapter)
    chapter_text = read_text(chapter_file) if chapter_file else ""
    quote_errors = _quote_errors(normalized["issues"], chapter_text)
    if quote_errors:
        report["status"] = "fail"
        report["errors"].extend(quote_errors)
        result["status"] = "invalid"
        result["report"] = report
        return result

    result["status"] = "blocked" if normalized["blocking_count"] else "pass"
    return result


def _issue_lines(issue: dict[str, Any]) -> list[str]:
    label = DIMENSION_LABELS.get(issue["dimension"], issue["dimension"])
    location = f"（{issue['location']}）" if issue["location"] else ""
    assessment = f" [{issue['assessment']}]" if issue.get("assessment") not in {None, "", "issue"} else ""
    code = f" · {issue['code']}" if issue.get("code") else ""
    lines = [f"- **[{issue['severity']}] {issue['id']} · {label}**{location}{assessment}{code}"]
    if issue["evidence"]:
        lines.append(f"  - 证据：{issue['evidence']}")
    for ref in issue.get("source_refs") or []:
        quote = ref["quote"].replace("\n", " ")
        if len(quote) > 160:
            quote = quote[:160] + "…"
        range_text = ""
        if ref.get("start_line") and ref.get("end_line"):
            range_text = f"（第 {ref['start_line']}-{ref['end_line']} 行）"
        lines.append(f"  - 原文{range_text}：{quote}")
    if issue["impact"]:
        lines.append(f"  - 影响：{issue['impact']}")
    if issue["repair"]:
        lines.append(f"  - 修复：{issue['repair']}")
    return lines


def render_review_markdown(payload: Any, *, chapter: int | None = None) -> str:
    """Render a human-readable report from the canonical JSON payload."""
    review = normalize_review_result(payload, chapter=chapter)
    status_label = "通过" if review["status"] == "pass" else "阻断"
    target = review["target"]
    lines = [
        f"# 第{review['chapter']}章 审稿报告",
        "",
        f"> 总评：**{review['grade'] or '未评级'}** · 状态：**{status_label}** · "
        f"blocking：**{review['blocking_count']}**",
        f"> 生成时间：{review['generated_at']}",
    ]
    if target.get("sha256"):
        digest = target["sha256"][:16]
        revision = target.get("revision_id") or "未绑定 revision"
        lines.append(
            f"> 审稿目标：`{target.get('chapter_file') or '未知文件'}` · sha256 `{digest}…` · {revision}"
        )
    basis = review.get("basis") or {}
    if basis.get("input_fingerprint"):
        lines.append(
            f"> 审稿依据：`{basis.get('workflow', '')}/{basis.get('step', '')}` · "
            f"fingerprint `{basis['input_fingerprint'][:16]}…`"
        )
    lines.append("")
    if review["summary"]:
        lines.extend(["## 总评摘要", "", review["summary"], ""])

    lines.extend(["## 五维评分", "", "| 维度 | 分数 | 摘要 |", "|---|---|---|"])
    for name in REVIEW_DIMENSIONS:
        item = review["dimensions"][name]
        score = "—" if item["score"] is None else f"{item['score']}/10"
        summary = item["summary"].replace("|", "\\|") or "—"
        lines.append(f"| {DIMENSION_LABELS[name]} | {score} | {summary} |")
    lines.append("")

    grouped = {severity: [] for severity in SEVERITIES}
    for issue in review["issues"]:
        grouped.setdefault(issue["severity"], []).append(issue)

    lines.extend(["## 问题清单", ""])
    if not review["issues"]:
        lines.append("无问题。")
        lines.append("")
    extra_severities = sorted(key for key in grouped if key not in SEVERITIES)
    titles = {
        "blocker": "Blocking（必须修复）",
        "major": "Major（建议修复）",
        "minor": "Minor（可选）",
    }
    for severity in [*SEVERITIES, *extra_severities]:
        items = grouped.get(severity, [])
        if not items:
            continue
        title = titles.get(severity, f"{severity}（未识别严重度）")
        lines.extend([f"### {title}", ""])
        for issue in items:
            lines.extend(_issue_lines(issue))
        lines.append("")

    if review["blocking_count"]:
        lines.extend(
            [
                "## 交付结论",
                "",
                f"存在 {review['blocking_count']} 个 blocking issue，"
                "`write_pipeline.py post` 的 quality 与 commit 阶段会阻断。"
                "按 repair 逐项修复后重新审稿。",
                "",
            ]
        )
    else:
        lines.extend(["## 交付结论", "", "无 blocking issue，可进入 commit 阶段。", ""])
    return "\n".join(lines).rstrip() + "\n"
