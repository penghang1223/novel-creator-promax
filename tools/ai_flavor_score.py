#!/usr/bin/env python3
"""Heuristic AI-flavor score (0-100) for Chinese prose.

Signals: sentence-length burstiness, repeated character n-grams, AI words,
dash/colon density, logic connectives and cliché phrases. This is a local
heuristic, not a platform detector.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from novel_creation_promax.core import thresholds as T  # noqa: E402

AI_WORDS = [
    "不禁", "缓缓", "淡淡", "微微", "仿佛", "似乎", "像是", "与此同时",
    "内心深处", "嘴角勾起", "命运的齿轮", "毋庸置疑", "显而易见",
    "众所周知", "不言而喻", "忍不住", "下意识", "不由自主", "一抹",
]
LOGIC_WORDS = [
    "因此", "所以", "然而", "但是", "不仅", "而且", "首先", "其次",
    "最后", "总之", "综上所述", "由此可见", "换句话说", "也就是说",
]
CLICHES = [
    "眼中闪过一丝", "嘴角勾起一抹", "心中一沉", "深吸一口气",
    "时间仿佛静止", "空气仿佛凝固", "心中五味杂陈", "如同一道惊雷",
    "瞳孔骤然收缩", "后背瞬间被冷汗浸透",
]


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except (FileNotFoundError, UnicodeDecodeError):
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def sentences(text: str) -> list[str]:
    return [item.strip() for item in re.split(r"(?<=[。！？!?])", text) if item.strip()]


def count_hits(text: str, words: list[str]) -> int:
    return sum(text.count(word) for word in words)


def burstiness(text: str) -> tuple[float, float]:
    lengths = [len(re.findall(r"[一-鿿]", sentence)) for sentence in sentences(text)]
    lengths = [value for value in lengths if value > 0]
    if len(lengths) < 5:
        return 5.0, 0.0
    mean = statistics.mean(lengths)
    stdev = statistics.pstdev(lengths)
    cv = stdev / mean if mean else 0
    score = max(0.0, min(10.0, 10 - cv * 12))
    return score, cv


def repeat_score(text: str) -> tuple[float, float]:
    chinese = re.sub(r"[^一-鿿]", "", text)
    if len(chinese) < 100:
        return 0.0, 0.0
    bigrams = Counter(chinese[index:index + 2] for index in range(len(chinese) - 1))
    repeated = sum(1 for count in bigrams.values() if count >= 3)
    per_1000 = repeated / len(chinese) * 1000
    return min(10.0, per_1000 * 1.5), per_1000


def score(text: str) -> dict[str, Any]:
    chinese = max(1, len(re.findall(r"[一-鿿]", text)))
    burst, cv = burstiness(text)
    repeat, repeated_per_1000 = repeat_score(text)
    ai_hits = count_hits(text, AI_WORDS)
    logic_hits = count_hits(text, LOGIC_WORDS)
    cliche_hits = count_hits(text, CLICHES)
    dash_density = text.count("——") / chinese * 1000
    colon_density = max(0, text.count("：") - len(re.findall(r"\d{1,2}:\d{2}", text))) / chinese * 1000

    ai_word = min(10.0, ai_hits / chinese * 1000 * 3)
    logic = min(10.0, logic_hits * 1.5)
    cliche = min(10.0, cliche_hits * 2)
    dash = min(10.0, max(0.0, dash_density - T.DASH_PER_1000_MAX) * 4)
    colon = min(10.0, max(0.0, colon_density - T.COLON_PER_1000_MAX) * 10)

    total = round(
        (
            burst * 0.10
            + repeat * 0.05
            + ai_word * 0.45
            + dash * 0.05
            + colon * 0.05
            + logic * 0.15
            + cliche * 0.15
        )
        * 10,
        1,
    )
    level = "低" if total < 20 else "中" if total < T.AI_FLAVOR_WARN else "高" if total < T.AI_FLAVOR_HIGH else "极高"
    return {
        "score": total,
        "level": level,
        "signals": {
            "burstiness": round(burst, 1),
            "sentence_cv": round(cv, 2),
            "repeat": round(repeat, 1),
            "repeat_per_1000": round(repeated_per_1000, 2),
            "ai_words": round(ai_word, 1),
            "ai_word_hits": ai_hits,
            "dash_density": round(dash_density, 2),
            "colon_density": round(colon_density, 2),
            "logic": round(logic, 1),
            "logic_hits": logic_hits,
            "cliche": round(cliche, 1),
            "cliche_hits": cliche_hits,
        },
        "word_count": chinese,
    }


def render_text(result: dict[str, Any]) -> str:
    signals = result["signals"]
    return "\n".join(
        [
            f"AI 味评分: {result['score']}/100（{result['level']}）",
            f"- 句长突发性: {signals['burstiness']}/10（CV {signals['sentence_cv']}）",
            f"- 重复 n-gram: {signals['repeat']}/10（{signals['repeat_per_1000']}/千字）",
            f"- AI 词: {signals['ai_words']}/10（{signals['ai_word_hits']} 次）",
            f"- 破折号: {signals['dash_density']}/千字 · 冒号: {signals['colon_density']}/千字",
            f"- 逻辑词: {signals['logic']}/10（{signals['logic_hits']} 次）",
            f"- 套话: {signals['cliche']}/10（{signals['cliche_hits']} 次）",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="启发式 AI 味评分")
    parser.add_argument("path", help="章节文件")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--check", action="store_true", help="达到预警线时返回 1")
    args = parser.parse_args()

    path = Path(args.path).expanduser()
    try:
        text = read_text(path)
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    result = score(text)
    result["file"] = str(path)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render_text(result))
    if args.check and result["score"] >= T.AI_FLAVOR_WARN:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
