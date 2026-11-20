"""Chapter tension-curve contract and report helpers."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .jsonio import load_json, now_iso, save_json
from .paths import list_chapter_files

TENSION_SCHEMA_VERSION = "1.0"
TENSION_REPORT_DIR = Path("素材") / "tension"
_HIGH_TENSION_TERMS = ("危险", "杀", "死", "血", "逃", "追", "威胁", "暴露", "秘密", "震惊", "崩溃", "冲突", "警告", "恐惧", "阴谋", "爆炸", "失踪")
_LOW_TENSION_TERMS = ("平静", "安静", "微笑", "回家", "睡", "温柔", "阳光", "松了口气", "放松")


def tension_report_path(novel_dir: Path, chapter: int) -> Path:
    return novel_dir / TENSION_REPORT_DIR / f"chapter_{chapter:03d}_tension.json"


def _chapter_segments(text: str, *, max_segments: int = 8) -> list[str]:
    normalized = re.sub(r"\n\s*(?:\*{3,}|-{3,})\s*\n", "\n\n", text)
    paragraphs = [item.strip() for item in re.split(r"\n\s*\n+", normalized) if item.strip()]
    if len(paragraphs) <= max_segments:
        return paragraphs
    size = max(1, len(paragraphs) // max_segments)
    return ["\n".join(paragraphs[index:index + size]) for index in range(0, len(paragraphs), size)][:max_segments]


def estimate_tension_curve(text: str, *, chapter: int = 0) -> dict[str, Any]:
    """Estimate a curve from prose without claiming editorial approval."""
    segments = _chapter_segments(text)
    points: list[dict[str, Any]] = []
    for index, segment in enumerate(segments, start=1):
        high = sum(segment.count(term) for term in _HIGH_TENSION_TERMS)
        low = sum(segment.count(term) for term in _LOW_TENSION_TERMS)
        punctuation = segment.count("！") + segment.count("!") + segment.count("？") + segment.count("?")
        dialogue = segment.count("“") + segment.count('"') + segment.count("‘")
        value = 3.5 + min(3.5, high * 0.55) + min(1.2, punctuation * 0.12) + min(0.8, dialogue * 0.08) - min(1.8, low * 0.3)
        value = round(max(1.0, min(10.0, value)), 1)
        points.append({"label": f"segment_{index}", "value": value})
    return {
        "schema_version": TENSION_SCHEMA_VERSION,
        "generated_at": now_iso(),
        "chapter": chapter,
        "source": "heuristic",
        "estimated": True,
        "method": "keyword_punctuation_dialogue_v1",
        "confidence": "low",
        "points": points,
        "status": "estimated" if points else "unavailable",
        "warnings": ["启发式估算仅用于看板趋势，不等同于人工或模型审稿"],
    }


def estimate_chapter_tension(novel_dir: Path, chapter: int, *, save: bool = False, force: bool = False) -> dict[str, Any]:
    chapter_file = next((path for number, path in list_chapter_files(novel_dir) if number == chapter), None)
    if chapter_file is None:
        return {"chapter": chapter, "status": "unavailable", "error": "章节正文不存在"}
    report_path = tension_report_path(novel_dir, chapter)
    if report_path.is_file() and not force:
        existing = load_json(report_path, {})
        if isinstance(existing, dict):
            return {**existing, "reused": True, "report_path": str(report_path)}
    try:
        text = chapter_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return {"chapter": chapter, "status": "unavailable", "error": str(exc)}
    report = estimate_tension_curve(text, chapter=chapter)
    report["source_path"] = str(chapter_file)
    report["report_path"] = str(report_path)
    if save:
        save_json(report_path, report)
    return report


def load_tension_contract(novel_dir: Path) -> dict[str, Any]:
    state = load_json(novel_dir / "novel_state.json", {})
    configured = state.get("tension_contract", {}) if isinstance(state, dict) else {}
    if not isinstance(configured, dict):
        configured = {}
    return {
        "enabled": bool(configured.get("enabled", False)),
        "min_points": max(3, int(configured.get("min_points", 3) or 3)),
        "min_peak": min(10, max(1, int(configured.get("min_peak", 7) or 7))),
        "require_release": bool(configured.get("require_release", True)),
    }


def _curve_from_summary(summary: dict[str, Any]) -> list[dict[str, Any]]:
    metrics = summary.get("chapter_metrics", {})
    if not isinstance(metrics, dict):
        metrics = {}
    raw = metrics.get("tension_curve", summary.get("tension_curve", []))
    if not isinstance(raw, list):
        return []
    points: list[dict[str, Any]] = []
    for index, item in enumerate(raw, start=1):
        if isinstance(item, dict):
            label = str(item.get("label") or item.get("stage") or f"point_{index}")
            value = item.get("value", item.get("tension"))
        else:
            label = f"point_{index}"
            value = item
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            numeric = -1
        points.append({"label": label, "value": numeric})
    return points


def validate_tension_curve(summary: dict[str, Any], contract: dict[str, Any] | None = None) -> dict[str, Any]:
    contract = contract or {"enabled": False}
    points = _curve_from_summary(summary)
    report: dict[str, Any] = {
        "schema_version": TENSION_SCHEMA_VERSION,
        "generated_at": now_iso(),
        "chapter": summary.get("chapter", 0),
        "enabled": bool(contract.get("enabled", False)),
        "points": points,
        "status": "skipped",
        "errors": [],
        "warnings": [],
    }
    if not report["enabled"]:
        return report
    errors: list[str] = report["errors"]
    min_points = max(3, int(contract.get("min_points", 3) or 3))
    min_peak = min(10, max(1, int(contract.get("min_peak", 7) or 7)))
    if len(points) < min_points:
        errors.append(f"张力曲线至少需要 {min_points} 个点，当前 {len(points)} 个")
    values = [item["value"] for item in points]
    invalid = [value for value in values if not isinstance(value, (int, float)) or value < 1 or value > 10]
    if invalid:
        errors.append("张力值必须全部位于 1-10")
    if values and max(values) < min_peak:
        errors.append(f"张力峰值必须达到 {min_peak}，当前 {max(values):g}")
    if contract.get("require_release", True) and len(values) >= 2 and values[-1] >= max(values):
        errors.append("结尾张力必须低于峰值，形成释放或悬念落点")
    if len(values) >= 2 and max(values) - values[0] < 1:
        report["warnings"].append("张力曲线缺少明显上升")
    report["status"] = "fail" if errors else "pass"
    return report


def validate_chapter_tension(novel_dir: Path, chapter: int, *, save: bool = True) -> dict[str, Any]:
    summary_path = novel_dir / "摘要" / f"chapter_{chapter:03d}_summary.json"
    summary = load_json(summary_path, {})
    if not isinstance(summary, dict):
        summary = {}
    report = validate_tension_curve(summary, load_tension_contract(novel_dir))
    report["summary_path"] = str(summary_path)
    report["report_path"] = str(tension_report_path(novel_dir, chapter))
    if save:
        save_json(tension_report_path(novel_dir, chapter), report)
    return report
