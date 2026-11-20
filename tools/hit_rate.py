#!/usr/bin/env python3
"""15-dimension hit-rate model for project greenlighting.

Scores are 0-10. The weighted total is 0-100. The model applies three
anti-self-deception rules from the source method: too many perfect scores are
downgraded, veto dimensions cap the total, and ceiling dimensions cap it again.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from novel_creation_promax.core import thresholds as T  # noqa: E402

DIMENSIONS: dict[str, dict[str, Any]] = {
    "D1": {"label": "赛道热度", "weight": 7, "ceiling": True},
    "D2": {"label": "核心设定新鲜度", "weight": 7},
    "D3": {"label": "书名点击力", "weight": 7},
    "D4": {"label": "简介转化力", "weight": 9, "veto": True},
    "D5": {"label": "开篇300字", "weight": 7},
    "D6": {"label": "主角可跟随性", "weight": 6},
    "D7": {"label": "反差强度", "weight": 4},
    "D8": {"label": "人设纯度", "weight": 7},
    "D9": {"label": "爽点密度", "weight": 9},
    "D10": {"label": "阶梯可延展", "weight": 7},
    "D11": {"label": "钩子工程", "weight": 8, "ceiling": True},
    "D12": {"label": "情感刚需匹配", "weight": 6, "veto": True},
    "D13": {"label": "长线留存设计", "weight": 6, "ceiling": True},
    "D14": {"label": "差异化切口", "weight": 5},
    "D15": {"label": "合规与平台适配", "weight": 5},
}


def _parse_scores(payload: Any) -> tuple[str, dict[str, float], dict[str, str]]:
    if not isinstance(payload, dict):
        raise ValueError("输入必须是 JSON 对象")
    title = str(payload.get("title") or "未命名项目")
    raw_scores = payload.get("scores") if isinstance(payload.get("scores"), dict) else payload
    reasons = payload.get("reasons") if isinstance(payload.get("reasons"), dict) else {}
    scores: dict[str, float] = {}
    for key in DIMENSIONS:
        value = raw_scores.get(key)
        if value is None:
            raise ValueError(f"缺少维度: {key} {DIMENSIONS[key]['label']}")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{key} 必须是 0-10 的数字")
        if value < 0 or value > 10:
            raise ValueError(f"{key} 超出范围 0-10: {value}")
        scores[key] = float(value)
    return title, scores, {str(key): str(value) for key, value in reasons.items()}


def _parse_markdown(text: str) -> tuple[str, dict[str, float], dict[str, str]]:
    title = "未命名项目"
    match = re.search(r"(?:书名|项目|标题)[:：]\s*(.+)", text)
    if match:
        title = match.group(1).strip()
    scores: dict[str, float] = {}
    reasons: dict[str, str] = {}
    for key, meta in DIMENSIONS.items():
        patterns = [
            rf"{key}\s*[^0-9\n]{{0,40}}?(\d+(?:\.\d+)?)",
            rf"{meta['label']}\s*[^0-9\n]{{0,20}}?(\d+(?:\.\d+)?)",
        ]
        for pattern in patterns:
            found = re.search(pattern, text)
            if found:
                scores[key] = float(found.group(1))
                break
    missing = [f"{key} {DIMENSIONS[key]['label']}" for key in DIMENSIONS if key not in scores]
    if missing:
        raise ValueError("Markdown 中缺少维度: " + "、".join(missing))
    return title, scores, reasons


def _apply_honesty(scores: dict[str, float]) -> tuple[dict[str, float], str]:
    perfect = [key for key, value in scores.items() if value >= 10]
    if len(perfect) <= 3:
        return scores, ""
    adjusted = {key: max(0.0, value - 1) for key, value in scores.items()}
    return adjusted, f"单维满分超过 3 项（{', '.join(perfect)}），全部下调一档"


def evaluate(payload: Any, *, honesty: bool = True) -> dict[str, Any]:
    title, scores, reasons = _parse_scores(payload) if isinstance(payload, dict) else _parse_markdown(str(payload))
    honesty_note = ""
    if honesty:
        scores, honesty_note = _apply_honesty(scores)

    total = round(sum(scores[key] * meta["weight"] for key, meta in DIMENSIONS.items()) / 10, 1)
    cap_reasons: list[str] = []
    for key, meta in DIMENSIONS.items():
        if meta.get("veto") and scores[key] == 0:
            total = min(total, T.HIT_VETO_CAP)
            cap_reasons.append(f"否决项 {key} {meta['label']} 得 0 分 → 封顶 {T.HIT_VETO_CAP}")
    for key, meta in DIMENSIONS.items():
        if meta.get("ceiling") and scores[key] <= 2:
            total = min(total, T.HIT_CEILING_CAP)
            cap_reasons.append(f"天花板项 {key} {meta['label']} ≤2 分 → 封顶 {T.HIT_CEILING_CAP}")

    if total >= T.HIT_RATE_GO:
        recommendation = "可开工"
    elif total >= T.HIT_RATE_FIX:
        recommendation = "补最弱两维再开工"
    elif total >= T.HIT_RATE_REBUILD:
        recommendation = "重构选题"
    else:
        recommendation = "换题"

    weakest = sorted(
        scores,
        key=lambda key: (scores[key], -DIMENSIONS[key]["weight"], key),
    )[:2]
    return {
        "title": title,
        "total": total,
        "recommendation": recommendation,
        "scores": scores,
        "weakest": weakest,
        "cap_reasons": cap_reasons,
        "honesty_adjustment": honesty_note,
        "reasons": reasons,
    }


def render_text(result: dict[str, Any]) -> str:
    lines = [
        f"项目: {result['title']}",
        f"命中率: {result['total']}/100 → {result['recommendation']}",
    ]
    for key, meta in DIMENSIONS.items():
        lines.append(
            f"- {key} {meta['label']}: {result['scores'][key]:g}/10 (权重 {meta['weight']}%)"
        )
    if result["weakest"]:
        lines.append(
            "最弱两维: "
            + "、".join(f"{key} {DIMENSIONS[key]['label']}" for key in result["weakest"])
        )
    if result["cap_reasons"]:
        lines.append("封顶原因: " + "；".join(result["cap_reasons"]))
    if result["honesty_adjustment"]:
        lines.append("防自欺调整: " + result["honesty_adjustment"])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="15 维爆款命中率评分")
    parser.add_argument("--input", required=True, help="立项书 JSON 或 Markdown")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-honesty", action="store_true", help="关闭「满分过多自动下调」规则")
    args = parser.parse_args()

    path = Path(args.input).expanduser()
    try:
        text = path.read_text(encoding="utf-8")
        payload: Any
        if path.suffix.lower() == ".json":
            payload = json.loads(text)
        else:
            payload = text
        result = evaluate(payload, honesty=not args.no_honesty)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render_text(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
