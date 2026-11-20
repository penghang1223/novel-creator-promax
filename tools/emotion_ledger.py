#!/usr/bin/env python3
"""Derived emotion ledger from chapter summaries.

Tracks temperature, cool-point type, suffering streak and last release chapter
so long serials do not stay suffocating for too long. The source of truth is
``摘要/chapter_*_summary.json``; the ledger is a rebuildable read model.
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

from novel_creation_promax.core.jsonio import load_json, save_json  # noqa: E402

RELEASE_WORDS = [
    "打脸", "反击", "逆转", "碾压", "爆发", "赢", "救", "解决", "突破",
    "翻身", "爽", "燃", "揭露", "真相", "成功", "兑现",
]
SUFFERING_WORDS = [
    "受辱", "憋屈", "失败", "失去", "被欺", "危险", "绝望", "痛", "惨",
    "欺负", "嘲笑", "羞辱", "压", "冷", "悲", "困", "逼",
]
HIGH_LABELS = ["爽", "燃", "爆", "惊", "转", "高", "张", "怒", "喜", "胜"]
LOW_LABELS = ["压", "沉", "冷", "痛", "悲", "抑", "惧", "慌", "困"]
SPARK_PATTERNS = [
    ("身份反转", ["身份", "掉马", "原来", "竟然是", "揭示", "伪装"]),
    ("打脸", ["打脸", "反击", "碾压", "刮目", "悔恨"]),
    ("信息差", ["秘密", "隐瞒", "发现", "证据", "信息", "线索"]),
    ("关系推进", ["信任", "和解", "表白", "关系", "靠近", "同盟"]),
    ("能力兑现", ["能力", "技能", "突破", "升级", "觉醒", "解锁"]),
    ("生死博弈", ["生死", "追杀", "危险", "救", "命", "逃"]),
    ("日常锚点", ["日常", "吃饭", "聊天", "休息", "生活"]),
]


def summaries(novel_dir: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for path in sorted((novel_dir / "摘要").glob("chapter_*_summary.json")):
        payload = load_json(path, {})
        if not isinstance(payload, dict):
            continue
        chapter = payload.get("chapter") or payload.get("chapter_number")
        if chapter is None:
            match = re.search(r"chapter_(\d+)_summary", path.name)
            chapter = int(match.group(1)) if match else 0
        payload["__chapter"] = int(chapter or 0)
        payload["__path"] = path
        result.append(payload)
    result.sort(key=lambda item: item["__chapter"])
    return result


def clamp(value: float, low: float = 1.0, high: float = 10.0) -> float:
    return max(low, min(high, value))


def estimate_tension(summary: dict[str, Any]) -> float:
    metrics = summary.get("chapter_metrics") or {}
    peak = metrics.get("tension_peak")
    if isinstance(peak, (int, float)) and not isinstance(peak, bool):
        return clamp(float(peak))
    curve = str(metrics.get("emotion_curve") or "")
    labels = [part for part in re.split(r"[—\-/、,，\s]+", curve) if part]
    high = sum(1 for label in labels if any(word in label for word in HIGH_LABELS))
    low = sum(1 for label in labels if any(word in label for word in LOW_LABELS))
    if high or low:
        return clamp(5 + high * 1.5 - low)
    return 5.0


def _text(summary: dict[str, Any]) -> str:
    parts = [str(summary.get("summary") or "")]
    parts.extend(str(item) for item in summary.get("key_events") or [])
    parts.extend(str(item) for item in summary.get("unresolved_questions") or [])
    metrics = summary.get("chapter_metrics") or {}
    parts.append(str(metrics.get("emotion_curve") or ""))
    return " ".join(parts)


def detect_spark(text: str) -> str:
    for name, words in SPARK_PATTERNS:
        if any(word in text for word in words):
            return name
    return "日常锚点"


def temperature(tension: float) -> str:
    if tension >= 8:
        return "高"
    if tension >= 5:
        return "中"
    return "低"


def build_ledger(novel_dir: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    streak = 0
    last_release: int | None = None
    for summary in summaries(novel_dir):
        chapter = summary["__chapter"]
        text = _text(summary)
        tension = estimate_tension(summary)
        release = any(word in text for word in RELEASE_WORDS)
        suffering = any(word in text for word in SUFFERING_WORDS) or tension <= 4
        if release:
            streak = 0
            last_release = chapter
        elif suffering:
            streak += 1
        spark_type = detect_spark(text)
        if suffering and not release:
            spark_type = "受辱/铺垫"
        rows.append(
            {
                "chapter": chapter,
                "title": str(summary.get("title") or ""),
                "tension": round(tension, 1),
                "temperature": temperature(tension),
                "spark_type": spark_type,
                "release": release,
                "suffering": suffering,
                "suffering_streak": streak,
                "last_release_chapter": last_release,
            }
        )

    warnings: list[str] = []
    if rows:
        max_streak = max(row["suffering_streak"] for row in rows)
        if max_streak > 3:
            warnings.append(f"憋屈累计 {max_streak} 章未释放（上限 3）")
        recent = rows[-5:]
        if len(recent) == 5 and len({row["temperature"] for row in recent}) == 1:
            warnings.append(f"最近 5 章温度同为「{recent[-1]['temperature']}」，读者可能疲劳")
        if last_release is not None and rows[-1]["chapter"] - last_release > 5:
            warnings.append(f"距上次释放已 {rows[-1]['chapter'] - last_release} 章")

    return {
        "schema_version": "1.0",
        "chapters": rows,
        "stats": {
            "chapters": len(rows),
            "max_suffering_streak": max((row["suffering_streak"] for row in rows), default=0),
            "last_release_chapter": last_release,
            "temperature_counts": {
                label: sum(1 for row in rows if row["temperature"] == label)
                for label in ("高", "中", "低")
            },
        },
        "warnings": warnings,
    }


def render_markdown(ledger: dict[str, Any]) -> str:
    lines = [
        "# 情绪账",
        "",
        "> 自动生成，禁止手改；源数据是 `摘要/chapter_*_summary.json`。",
        "",
        "| 章号 | 温度档 | 爽点类型 | 憋屈累计 | 上次释放 |",
        "|---|---|---|---|---|",
    ]
    for row in ledger["chapters"]:
        lines.append(
            f"| {row['chapter']} | {row['temperature']} | {row['spark_type']} | "
            f"{row['suffering_streak']} | {row['last_release_chapter'] or '—'} |"
        )
    if ledger["warnings"]:
        lines.extend(["", "## 预警", ""])
        for warning in ledger["warnings"]:
            lines.append(f"- {warning}")
    return "\n".join(lines).rstrip() + "\n"


def cmd_sync(args: argparse.Namespace) -> int:
    novel_dir = Path(args.novel_dir).expanduser().resolve()
    ledger = build_ledger(novel_dir)
    save_json(novel_dir / "摘要" / "emotion_ledger.json", ledger)
    view = novel_dir / "追踪" / "情绪账.md"
    view.parent.mkdir(parents=True, exist_ok=True)
    view.write_text(render_markdown(ledger), encoding="utf-8")
    print(f"[OK] 情绪账: {view}")
    for warning in ledger["warnings"]:
        print(f"[WARN] {warning}", file=sys.stderr)
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    novel_dir = Path(args.novel_dir).expanduser().resolve()
    ledger = build_ledger(novel_dir)
    if args.json:
        print(json.dumps(ledger, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(ledger), end="")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="情绪账：温度档、憋屈累计、上次释放")
    sub = parser.add_subparsers(dest="command", required=True)
    sync = sub.add_parser("sync", help="从章节摘要重建情绪账")
    sync.add_argument("--novel-dir", required=True)
    sync.set_defaults(func=cmd_sync)
    show = sub.add_parser("show", help="查看当前情绪账")
    show.add_argument("--novel-dir", required=True)
    show.add_argument("--json", action="store_true")
    show.set_defaults(func=cmd_show)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
