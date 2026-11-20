#!/usr/bin/env python3
"""Weighted five-dimension score for one novel idea card.

Weights follow ``knowledge_base/50_Quality/创意五维评分.md``:
innovation 10%, market 25%, readability 20%, emotion 25%, commercial 20%.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

WEIGHTS = {
    "innovation": 0.10,
    "market": 0.25,
    "readability": 0.20,
    "emotion": 0.25,
    "commercial": 0.20,
}
LABELS = {
    "innovation": "创新性",
    "market": "市场潜力",
    "readability": "可读性",
    "emotion": "情绪价值",
    "commercial": "商业价值",
}
GRADES = ((85, "S"), (75, "A"), (65, "B"), (55, "C"))


def _validate(payload: Any) -> dict[str, float]:
    if not isinstance(payload, dict):
        raise ValueError("输入必须是 JSON 对象")
    scores = payload.get("scores")
    if not isinstance(scores, dict):
        raise ValueError("缺少 scores 对象")

    missing = [key for key in WEIGHTS if key not in scores]
    if missing:
        raise ValueError(f"缺少维度: {', '.join(missing)}")

    values: dict[str, float] = {}
    for key in WEIGHTS:
        value = scores[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{LABELS[key]} 必须是 0-10 的数字")
        if value < 0 or value > 10:
            raise ValueError(f"{LABELS[key]} 超出范围 0-10: {value}")
        values[key] = float(value)
    return values


def score_idea(payload: dict[str, Any]) -> dict[str, Any]:
    values = _validate(payload)
    total = round(sum(values[key] * WEIGHTS[key] * 10 for key in WEIGHTS), 1)
    grade = next((label for threshold, label in GRADES if total >= threshold), "D")
    weakest = sorted(
        (key for key, value in values.items() if value < 8),
        key=lambda key: (values[key], key),
    )

    if total >= 75 and not weakest:
        recommendation = "可进入立项"
    elif total >= 60:
        names = "、".join(LABELS[key] for key in weakest) or "短板维度"
        recommendation = f"可立项，但先补强：{names}"
    else:
        names = "、".join(LABELS[key] for key in weakest) or "整体创意"
        recommendation = f"不建议直接立项；先重做或补强：{names}"

    return {
        "title": str(payload.get("title") or "未命名创意"),
        "total": total,
        "grade": grade,
        "dimension_scores": values,
        "weakest": weakest,
        "recommendation": recommendation,
    }


def _render_text(result: dict[str, Any]) -> str:
    lines = [
        f"创意: {result['title']}",
        f"总分: {result['total']}/100 | 等级: {result['grade']}",
    ]
    for key, value in result["dimension_scores"].items():
        lines.append(f"- {LABELS[key]}: {value:g}/10 (权重 {WEIGHTS[key]:.0%})")
    if result["weakest"]:
        lines.append("短板: " + "、".join(LABELS[key] for key in result["weakest"]))
    lines.append(f"建议: {result['recommendation']}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="创意五维评分")
    parser.add_argument("--input", required=True, help="创意卡 JSON 文件")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    try:
        payload = json.loads(Path(args.input).expanduser().read_text(encoding="utf-8"))
        result = score_idea(payload)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(_render_text(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
