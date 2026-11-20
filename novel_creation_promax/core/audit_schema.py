"""Canonical audit-report schema and readers.

历史原因，审计报告存在两种落盘格式：

1. **legacy（扁平）**  —— 老版本 ``post_write_audit.py`` 直接写顶层键：
   ``{"ai_words": {"突然": 3}, "dialogue_ratio": 0.31, "word_count": 2950,
     "pass": true, "warnings": [...]}``
2. **wrapped（嵌套）**  —— 当前版本写成 ``{"generated_at","status","results":{...}}``

另有多个历史文件名/目录（``audit_ch22.json`` / ``audit_ch022.json`` /
``chapter_022_audit.json``，``素材/`` 或 ``摘要/``）。

本模块提供**唯一**的读取入口：``load_audit()`` 返回统一的 canonical dict，
消费方（``write_pipeline.generate_fix_plan`` / ``governance_check`` /
``audit_dashboard`` / ``chapter_guard``）一律只读 canonical 结构，不再各自
``audit.get(...)`` 猜格式。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .jsonio import load_json
from .passport import normalize_status

AUDIT_DIRS = ("素材", "摘要")
# 按优先级尝试的文件名模板（chapter 同时用零填充与非填充两种）
AUDIT_NAME_TEMPLATES = (
    "audit_ch{chapter:03d}.json",
    "audit_ch{chapter}.json",
    "chapter_{chapter:03d}_audit.json",
    "audit_{chapter:03d}_report.json",
)


def _required_keys(obj: Any) -> bool:
    return isinstance(obj, dict) and any(
        key in obj for key in ("ai_words", "dialogue_ratio", "word_count", "pass", "status", "warnings")
    )


def find_audit_report(novel_dir: Path, chapter: int) -> Path | None:
    """定位某章审计报告，兼容历史文件名与目录。"""
    candidates: list[Path] = []
    for sub in AUDIT_DIRS:
        for template in AUDIT_NAME_TEMPLATES:
            candidates.append(novel_dir / sub / template.format(chapter=chapter))
    for path in candidates:
        if path.exists():
            return path
    # 兜底：目录里可能有不符合模板的命名，按章号正则匹配
    for sub in AUDIT_DIRS:
        directory = novel_dir / sub
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*audit*.json")):
            numbers = [int(n) for n in re.findall(r"\d+", path.stem)]
            if chapter in numbers:
                return path
    return None


def unwrap_audit(payload: Any) -> dict[str, Any]:
    """把 legacy / wrapped 两种格式统一成扁平 dict，保留原始元数据。"""
    if not isinstance(payload, dict):
        return {}
    results = payload.get("results")
    if isinstance(results, dict) and _required_keys(results):
        flat = dict(results)
        flat.setdefault("generated_at", payload.get("generated_at", ""))
        flat["_wrapper_status"] = payload.get("status", "")
        flat["_format"] = "wrapped"
        return flat
    flat = dict(payload)
    flat.setdefault("_format", "legacy")
    return flat


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, dict):
        for key in ("count", "value", "word_count", "chars"):
            if key in value:
                return _as_int(value[key])
    return None


def _ai_word_items(raw: Any) -> list[dict[str, Any]]:
    """把多种 AI 词结构统一成 [{"word","count"}]。"""
    items: list[dict[str, Any]] = []
    if isinstance(raw, dict):
        # 形式 A: {"突然": 3}；形式 B: {"found": ["突然", ...]}
        for key in ("found", "detected", "words", "list"):
            value = raw.get(key)
            if isinstance(value, list):
                for word in value:
                    items.append({"word": str(word), "count": 1})
                return items
        for word, count in raw.items():
            number = _as_int(count)
            if number is None or number <= 0:
                continue
            items.append({"word": str(word), "count": number})
        return items
    if isinstance(raw, list):
        for entry in raw:
            if isinstance(entry, str):
                items.append({"word": entry, "count": 1})
            elif isinstance(entry, dict):
                word = entry.get("word") or entry.get("name") or entry.get("text")
                if word:
                    items.append({"word": str(word), "count": _as_int(entry.get("count")) or 1})
    return items


def canonicalize(flat: dict[str, Any], *, chapter: int | None = None, source: Path | None = None) -> dict[str, Any]:
    """把 unwrap 后的扁平 dict 转成 canonical audit 结构。

    以原始字段为基础（保留 style_drift / writing_gate 等扩展字段），
    再用规范化后的值覆盖易变字段，保证消费方有稳定契约。
    """
    status_raw = flat.get("_wrapper_status") or flat.get("status") or flat.get("overall_status")
    if status_raw:
        status = normalize_status(status_raw)
    elif "pass" in flat:
        status = normalize_status(flat.get("pass"))
    else:
        status = "pending"

    dialogue_raw = flat.get("dialogue_ratio")
    if isinstance(dialogue_raw, dict):
        dialogue = _as_float(dialogue_raw.get("ratio", dialogue_raw.get("value")))
    else:
        dialogue = _as_float(dialogue_raw)

    warnings = flat.get("warnings")
    if not isinstance(warnings, list):
        warnings = []
    concentration = flat.get("concentration_issues")
    if not isinstance(concentration, list):
        concentration = []

    ai_items = _ai_word_items(flat.get("ai_words", flat.get("banned_words")))
    total_ai = _as_int(flat.get("total_ai_words"))
    if total_ai is None:
        total_ai = sum(item["count"] for item in ai_items)

    canonical = dict(flat)
    canonical.update(
        {
            "chapter": chapter,
            "status": status,
            "passed": status == "pass",
            "ai_words": ai_items,
            "ai_word_count": sum(item["count"] for item in ai_items),
            "total_ai_words": total_ai,
            "dialogue_ratio": dialogue,
            "word_count": _as_int(flat.get("word_count")),
            "warnings": [str(w) for w in warnings],
            "concentration_issues": [str(w) for w in concentration],
            "generated_at": str(flat.get("generated_at", "")),
            "format": str(flat.get("_format", "legacy")),
            "source_file": source.as_posix() if source else "",
        }
    )
    return canonical


def load_audit(novel_dir: Path, chapter: int) -> dict[str, Any] | None:
    """读取某章审计报告并返回 canonical 结构；不存在时返回 None。"""
    path = find_audit_report(novel_dir, chapter)
    if path is None:
        return None
    payload = load_json(path, {})
    flat = unwrap_audit(payload)
    if not flat:
        return None
    return canonicalize(flat, chapter=chapter, source=path)


def load_audit_all(novel_dir: Path, upto: int | None = None) -> list[dict[str, Any]]:
    """按章号升序加载所有可读审计报告。"""
    reports: list[dict[str, Any]] = []
    for sub in AUDIT_DIRS:
        directory = novel_dir / sub
        if not directory.is_dir():
            continue
        for path in directory.glob("*audit*.json"):
            numbers = [int(n) for n in re.findall(r"\d+", path.stem)]
            if not numbers:
                continue
            chapter = numbers[-1]
            if upto is not None and chapter > upto:
                continue
            report = load_audit(novel_dir, chapter)
            if report is not None:
                reports.append(report)
    dedup: dict[int, dict[str, Any]] = {}
    for report in reports:
        chapter = report.get("chapter")
        if isinstance(chapter, int) and chapter not in dedup:
            dedup[chapter] = report
    return [dedup[key] for key in sorted(dedup)]
