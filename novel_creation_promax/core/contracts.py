"""Lossless, dependency-free validation for the project's JSON contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .jsonio import load_json, now_iso, save_json
from .passport import ensure_passport_shape, passport_path
from .project_state import ensure_state_shape

CONTRACT_SCHEMA_VERSION = "1.0"


def _report(name: str) -> dict[str, Any]:
    return {"contract": name, "status": "pass", "errors": [], "warnings": []}


def validate_chapter_summary(payload: Any, *, chapter: int | None = None, strict: bool = False) -> dict[str, Any]:
    report = _report("chapter_summary")
    if not isinstance(payload, dict):
        report["status"] = "fail"
        report["errors"].append("摘要必须是 JSON 对象")
        return report
    if chapter is not None and payload.get("chapter") not in {None, chapter}:
        report["errors"].append(f"章号不匹配: expected={chapter}, actual={payload.get('chapter')}")
    elif chapter is not None and "chapter" not in payload:
        report["warnings"].append("缺少 chapter，将由文件路径推断")
    if strict:
        for key in ("chapter", "summary", "key_events"):
            if key not in payload:
                report["errors"].append(f"缺少字段: {key}")
    if "summary" in payload and not isinstance(payload.get("summary"), str):
        report["errors"].append("summary 必须是字符串")
    for key in ("key_events", "foreshadowing_planted", "foreshadowing_resolved", "unresolved_questions"):
        if key in payload and not isinstance(payload.get(key), list):
            report["errors"].append(f"{key} 必须是数组")
    metrics = payload.get("chapter_metrics")
    if metrics is not None and not isinstance(metrics, dict):
        report["errors"].append("chapter_metrics 必须是对象")
    strand = payload.get("strand")
    if strand is not None and not isinstance(strand, dict):
        report["errors"].append("strand 必须是对象")
    report["status"] = "fail" if report["errors"] else "pass"
    return report


def validate_passport(payload: Any, *, chapter: int | None = None) -> dict[str, Any]:
    report = _report("chapter_passport")
    if not isinstance(payload, dict):
        report["status"] = "fail"
        report["errors"].append("passport 必须是 JSON 对象")
        return report
    if chapter is not None and payload.get("chapter") not in {None, chapter}:
        report["errors"].append(f"章号不匹配: expected={chapter}, actual={payload.get('chapter')}")
    elif chapter is not None and "chapter" not in payload:
        report["warnings"].append("缺少 chapter，将由 passport 文件名推断")
    if "pipeline" in payload and not isinstance(payload.get("pipeline"), dict):
        report["errors"].append("pipeline 必须是对象")
    elif "pipeline" not in payload:
        report["warnings"].append("缺少 pipeline，将由 passport 兼容层补齐")
    if "inputs" in payload and not isinstance(payload.get("inputs"), dict):
        report["errors"].append("inputs 必须是对象")
    elif "inputs" not in payload:
        report["warnings"].append("缺少 inputs，将由 passport 兼容层补齐")
    if payload.get("schema_version") not in {None, "1.0", "1.1", "1.2"}:
        report["errors"].append(f"不支持的 passport schema_version: {payload.get('schema_version')}")
    report["status"] = "fail" if report["errors"] else "pass"
    return report


def validate_project_state(payload: Any) -> dict[str, Any]:
    report = _report("novel_state")
    if not isinstance(payload, dict):
        report["status"] = "fail"
        report["errors"].append("novel_state 必须是 JSON 对象")
        return report
    for key in ("current_chapter", "last_completed_chapter", "word_count"):
        if key in payload and not isinstance(payload.get(key), int):
            report["errors"].append(f"{key} 必须是整数")
    if "chapters" in payload and not isinstance(payload.get("chapters"), dict):
        report["errors"].append("chapters 必须是对象")
    if "tension_contract" in payload and not isinstance(payload.get("tension_contract"), dict):
        report["errors"].append("tension_contract 必须是对象")
    report["status"] = "fail" if report["errors"] else "pass"
    return report


def validate_chapter_contracts(novel_dir: Path, chapter: int, *, passport: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate existing chapter artifacts without mutating source files."""
    summary_path = novel_dir / "摘要" / f"chapter_{chapter:03d}_summary.json"
    state_path = novel_dir / "novel_state.json"
    passport_payload = passport if passport is not None else load_json(passport_path(novel_dir, chapter), {})
    checks = [validate_passport(passport_payload, chapter=chapter)]
    if summary_path.is_file():
        checks.append(validate_chapter_summary(load_json(summary_path, {}), chapter=chapter, strict=False))
    else:
        checks.append({**_report("chapter_summary"), "status": "skipped", "warnings": [f"摘要不存在: {summary_path.name}"]})
    if state_path.is_file():
        checks.append(validate_project_state(load_json(state_path, {})))
    else:
        checks.append({**_report("novel_state"), "status": "skipped", "warnings": ["novel_state.json 不存在"]})
    errors = [f"{item['contract']}: {error}" for item in checks for error in item.get("errors", [])]
    warnings = [f"{item['contract']}: {warning}" for item in checks for warning in item.get("warnings", [])]
    return {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "generated_at": now_iso(),
        "chapter": chapter,
        "status": "fail" if errors else "pass",
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
    }


def save_contract_report(novel_dir: Path, chapter: int, report: dict[str, Any]) -> Path:
    path = novel_dir / "素材" / "contracts" / f"chapter_{chapter:03d}_contracts.json"
    save_json(path, report)
    return path
