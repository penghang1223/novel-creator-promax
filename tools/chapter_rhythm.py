#!/usr/bin/env python3
"""Cross-chapter rhythm checks R1-R8 from a chapter operations table.

Expected Markdown columns (header names are matched loosely):

| 章 | 爽点类型 | 钩子强度 | 字数 |
|---|---|---|---|
| 1 | 身份反转 | 强 | 3000 |
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

HIGH_SPARKS = {"身份反转", "打脸", "能力兑现", "生死博弈"}
BIG_SPARKS = {"身份反转", "生死博弈"}
RELEASE_SPARKS = {"身份反转", "打脸", "能力兑现", "生死博弈"}
SUFFERING_SPARKS = {"受辱/铺垫"}


def _cell(value: str) -> str:
    return value.strip().strip("*` ").strip()


def normalize_spark(value: str) -> str:
    text = _cell(value)
    mapping = [
        ("身份反转", ["身份", "掉马", "马甲", "伪装", "原来"]),
        ("打脸", ["打脸", "反击", "碾压", "羞辱", "悔恨"]),
        ("信息差", ["信息", "秘密", "隐瞒", "证据", "线索"]),
        ("关系推进", ["关系", "感情", "信任", "和解", "表白"]),
        ("能力兑现", ["能力", "技能", "升级", "突破", "觉醒"]),
        ("生死博弈", ["生死", "危机", "追杀", "逃", "救"]),
        ("受辱/铺垫", ["受辱", "憋屈", "压", "铺垫", "惨"]),
    ]
    for label, words in mapping:
        if any(word in text for word in words):
            return label
    return text or "日常锚点"


def normalize_hook(value: str) -> str:
    text = _cell(value)
    if "强" in text or "高" in text:
        return "强"
    if "弱" in text or "低" in text or "平" in text:
        return "弱"
    return "中"


def parse_table(text: str) -> list[dict[str, Any]]:
    lines = [line for line in text.splitlines() if line.strip().startswith("|")]
    if not lines:
        raise ValueError("未找到 Markdown 表格")
    headers = [_cell(cell) for cell in lines[0].strip("|").split("|")]
    fields = {
        "chapter": ("章", "章节", "chapter"),
        "spark": ("爽点", "类型", "spark"),
        "hook": ("钩子", "hook"),
        "words": ("字数", "词数", "words"),
    }
    indexes: dict[str, int] = {}
    for key, candidates in fields.items():
        for index, header in enumerate(headers):
            if any(candidate in header for candidate in candidates):
                indexes[key] = index
                break
    if "chapter" not in indexes:
        indexes["chapter"] = 0
    rows: list[dict[str, Any]] = []
    for line in lines[2:]:
        cells = [_cell(cell) for cell in line.strip("|").split("|")]
        if len(cells) < len(headers):
            continue
        match = re.search(r"\d+", cells[indexes["chapter"]])
        if not match:
            continue
        chapter = int(match.group())
        spark = normalize_spark(cells[indexes["spark"]]) if "spark" in indexes and indexes["spark"] < len(cells) else "日常锚点"
        hook = normalize_hook(cells[indexes["hook"]]) if "hook" in indexes and indexes["hook"] < len(cells) else "中"
        word_text = cells[indexes["words"]] if "words" in indexes and indexes["words"] < len(cells) else ""
        word_match = re.search(r"\d+", word_text)
        rows.append(
            {
                "chapter": chapter,
                "spark": spark,
                "hook": hook,
                "words": int(word_match.group()) if word_match else 0,
            }
        )
    rows.sort(key=lambda item: item["chapter"])
    if not rows:
        raise ValueError("表格中没有有效章节行")
    return rows


def _windows(rows: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [rows[index:index + size] for index in range(0, max(0, len(rows) - size + 1))]


def check(rows: list[dict[str, Any]], *, platform: str = "") -> dict[str, Any]:
    issues: list[dict[str, Any]] = []

    def add(code: str, severity: str, message: str, chapters: list[int]) -> None:
        issues.append({"code": code, "severity": severity, "message": message, "chapters": chapters})

    for window in _windows(rows, T.RHYTHM_SMALL_CLIMAX_EVERY):
        if not any(row["spark"] in HIGH_SPARKS for row in window):
            add(
                "R1",
                "警告",
                f"第 {window[0]['chapter']}-{window[-1]['chapter']} 章连续 {len(window)} 章无高强度爽点",
                [row["chapter"] for row in window],
            )

    for window in _windows(rows, T.RHYTHM_BIG_REVERSAL_EVERY):
        if not any(row["spark"] in BIG_SPARKS for row in window):
            add(
                "R2",
                "警告",
                f"第 {window[0]['chapter']}-{window[-1]['chapter']} 章无身份反转或生死博弈",
                [row["chapter"] for row in window],
            )

    run = 1
    for index in range(1, len(rows)):
        if rows[index]["spark"] == rows[index - 1]["spark"]:
            run += 1
        else:
            run = 1
        if run == T.RHYTHM_SAME_COOLPOINT_STREAK:
            window = rows[index - run + 1:index + 1]
            add(
                "R3",
                "提示",
                f"第 {window[0]['chapter']}-{window[-1]['chapter']} 章连续同为「{window[-1]['spark']}」",
                [row["chapter"] for row in window],
            )

    run = 1
    for index in range(1, len(rows)):
        if rows[index]["hook"] == "弱" and rows[index - 1]["hook"] == "弱":
            run += 1
        else:
            run = 1
        if run == T.RHYTHM_WEAK_HOOK_STREAK:
            window = rows[index - run + 1:index + 1]
            add(
                "R4",
                "警告",
                f"第 {window[0]['chapter']}-{window[-1]['chapter']} 章连续弱钩子",
                [row["chapter"] for row in window],
            )

    first = rows[:T.RHYTHM_FIRST_CHAPTERS]
    if len(first) >= T.RHYTHM_FIRST_CHAPTERS and not any(row["spark"] in HIGH_SPARKS for row in first):
        add(
            "R5",
            "严重",
            "第 1-3 章未出现身份反转/生死博弈/打脸/能力兑现",
            [row["chapter"] for row in first],
        )

    identity = sum(1 for row in rows if row["spark"] == "身份反转")
    ratio = identity / len(rows) if rows else 0
    if ratio < T.RHYTHM_IDENTITY_REVEAL_MIN_RATIO:
        add(
            "R6",
            "提示",
            f"身份反转占比 {ratio:.0%}（建议 ≥{T.RHYTHM_IDENTITY_REVEAL_MIN_RATIO:.0%}）",
            [],
        )

    for index, row in enumerate(rows):
        if row["spark"] not in SUFFERING_SPARKS:
            continue
        window = rows[index + 1:index + 1 + T.RHYTHM_RELEASE_WINDOW]
        if window and not any(item["spark"] in RELEASE_SPARKS for item in window):
            add(
                "R7",
                "警告",
                f"第 {row['chapter']} 章憋屈后 {T.RHYTHM_RELEASE_WINDOW} 章内无释放",
                [row["chapter"]] + [item["chapter"] for item in window],
            )

    word_range = T.platform_word_range(platform)
    for row in rows:
        if row["words"] and not (word_range[0] <= row["words"] <= word_range[1]):
            add(
                "R8",
                "提示",
                f"第 {row['chapter']} 章字数 {row['words']}，建议 {word_range[0]}-{word_range[1]}",
                [row["chapter"]],
            )

    return {
        "schema_version": "1.0",
        "chapters": len(rows),
        "platform": platform or "generic",
        "word_range": list(word_range),
        "issues": issues,
        "stats": {
            "identity_reveal_ratio": round(ratio, 3),
            "high_spark_chapters": sum(1 for row in rows if row["spark"] in HIGH_SPARKS),
            "weak_hook_chapters": sum(1 for row in rows if row["hook"] == "弱"),
        },
    }


def render_text(result: dict[str, Any]) -> str:
    lines = [
        f"章节节奏 R1-R8：{result['chapters']} 章 · 平台 {result['platform']} · "
        f"字数区间 {result['word_range'][0]}-{result['word_range'][1]}",
    ]
    if not result["issues"]:
        lines.append("✅ 未发现节奏问题")
    for issue in result["issues"]:
        lines.append(f"[{issue['code']} {issue['severity']}] {issue['message']}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="章节节奏 R1-R8 检查")
    parser.add_argument("--table", required=True, help="章节作战表 Markdown")
    parser.add_argument("--platform", default="", help="番茄/起点/七猫/知乎，用于字数区间")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--check", action="store_true", help="存在严重问题时返回 1")
    args = parser.parse_args()

    path = Path(args.table).expanduser()
    try:
        rows = parse_table(path.read_text(encoding="utf-8"))
        result = check(rows, platform=args.platform)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render_text(result))
    if args.check and any(issue["severity"] == "严重" for issue in result["issues"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
