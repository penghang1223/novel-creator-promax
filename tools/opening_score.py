#!/usr/bin/env python3
"""Deterministic opening scorecard: four windows, eight modules, low-retention flags.

This is a heuristic first pass, not a replacement for human reading. It is
designed to catch the common opening failures that are visible in the text:
weather openings, information dumps, dream wakes, passive protagonists and
chapter ends that close the story.
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

GENRE_WORDS = [
    "玄幻", "修仙", "仙侠", "都市", "末世", "系统", "重生", "穿越", "悬疑",
    "规则怪谈", "无限流", "甜宠", "赘婿", "马甲", "电竞", "直播", "历史",
    "校园", "职场", "豪门", "替身", "克苏鲁", "西幻", "游戏",
]
MECHANISM_WORDS = [
    "系统", "面板", "技能", "天赋", "金手指", "空间", "重生", "穿越",
    "异能", "功法", "等级", "积分", "任务", "奖励", "冷却", "代价",
    "签到", "属性", "副本", "抽奖",
]
CONFLICT_WORDS = [
    "突然", "猛地", "却", "但是", "然而", "没想到", "竟然", "居然",
    "冲", "逃", "打", "杀", "追", "喊", "撞", "摔", "血", "疼",
    "危险", "失败", "失去", "欠", "逼", "威胁", "拒绝", "抢", "砸",
    "吵", "骂", "拦", "挡", "夺", "推",
]
ACTION_WORDS = [
    "走", "跑", "冲", "抓", "推", "拉", "扔", "踢", "拔", "按", "敲",
    "踹", "翻", "躲", "挡", "拦", "追", "逃", "喊", "问", "答", "看",
    "盯", "笑", "哭", "咬牙", "握紧", "回头", "站起", "坐下",
]
GOAL_WORDS = [
    "要", "必须", "得", "想", "需要", "不能", "否则", "为了", "打算",
    "决定", "目标", "只能", "一定",
]
COST_WORDS = [
    "代价", "失去", "赔", "罚", "扣", "欠", "死", "伤", "毁", "破产",
    "失业", "退学", "离婚", "坐牢", "封杀", "取消", "降级", "反噬",
]
INFO_DUMP_WORDS = [
    "这个世界", "大陆", "帝国", "王朝", "千年前", "万年前", "传说",
    "据说", "自古以来", "在这个时代", "众所周知",
]
WEATHER_WORDS = [
    "阳光", "天空", "云", "风", "雨", "雪", "清晨", "黄昏", "夜色",
    "月亮", "太阳", "天气",
]
DREAM_WORDS = ["睁开眼", "醒来", "做梦", "梦里", "梦中", "恍惚间"]
PASSIVE_WORDS = ["被", "任由", "只能", "不得不", "没有办法", "无能为力", "被迫"]
SUFFERING_WORDS = ["受辱", "憋屈", "失败", "失去", "被欺", "危险", "绝望", "痛", "惨", "欺负", "嘲笑", "羞辱"]
RELEASE_WORDS = ["打脸", "反转", "胜利", "爆发", "解决", "赢", "救", "反击", "翻身", "碾压", "突破"]
CHANGE_WORDS = ["但是", "然而", "却", "没想到", "结果", "于是", "突然", "就在这时", "下一刻"]
AI_WORDS = ["不禁", "缓缓", "淡淡", "微微", "仿佛", "似乎", "像是", "与此同时", "内心深处", "嘴角勾起"]
SELF_DISCOURAGE = ["本书慢热", "请耐心", "后面会", "前期铺垫", "慢热型"]


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except (FileNotFoundError, UnicodeDecodeError):
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def split_chapters(text: str) -> list[str]:
    parts = re.split(r"(?m)^\s*第[零一二三四五六七八九十百千万\d]+章[^\n]*\n", text)
    chapters = [part.strip() for part in parts if part.strip()]
    return chapters or [text.strip()]


def first_sentences(text: str, count: int = 3) -> str:
    sentences = re.split(r"(?<=[。！？!?])", text)
    return "".join(sentence for sentence in sentences[:count] if sentence).strip()


def count_hits(text: str, words: list[str]) -> int:
    return sum(text.count(word) for word in words)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def paragraph_lengths(text: str) -> list[int]:
    return [len(paragraph) for paragraph in re.split(r"\n\s*\n", text) if paragraph.strip()]


def module_a(front: str) -> tuple[int, str]:
    genre = count_hits(front, GENRE_WORDS)
    mechanism = count_hits(front, MECHANISM_WORDS)
    score = clamp(5 + genre * 2 + mechanism * 1.5, 0, 15)
    return int(score), f"题材词 {genre} / 机制词 {mechanism}"


def module_b(front: str) -> tuple[int, str]:
    goal = count_hits(front, GOAL_WORDS)
    action = count_hits(front, ACTION_WORDS)
    passive = count_hits(front, PASSIVE_WORDS)
    score = clamp(4 + goal * 2 + action * 1.2 - passive * 1.5, 0, 15)
    return int(score), f"目标 {goal} / 动作 {action} / 被动 {passive}"


def module_c(front: str) -> tuple[int, str]:
    conflict = count_hits(front, CONFLICT_WORDS)
    cost = count_hits(front, COST_WORDS)
    score = clamp(3 + conflict * 2 + cost * 2, 0, 15)
    return int(score), f"冲突 {conflict} / 代价 {cost}"


def module_d(ch1: str) -> tuple[int, str]:
    if len(ch1) < 400:
        return 5, "章节过短，无法判断局面变化"
    start = ch1[:200]
    end = ch1[-300:]
    change = count_hits(end, CHANGE_WORDS)
    new_info = 1 if end.strip() != start.strip() else 0
    score = clamp(4 + change * 2 + new_info * 3, 0, 15)
    return int(score), f"变化词 {change} / 首尾差异 {new_info}"


def module_e(three: str) -> tuple[int, str]:
    mechanism = count_hits(three, MECHANISM_WORDS)
    action = count_hits(three, ACTION_WORDS)
    cost = count_hits(three, COST_WORDS)
    score = clamp(3 + mechanism * 2 + action * 0.5 + cost * 1.5, 0, 15)
    return int(score), f"机制 {mechanism} / 动作 {action} / 代价 {cost}"


def module_f(front: str) -> tuple[int, str]:
    dump = count_hits(front, INFO_DUMP_WORDS)
    long_paragraphs = sum(1 for length in paragraph_lengths(front) if length > 180)
    names = len(re.findall(r"[一-龥]{2,3}(?:说|道|问|答|笑|站|坐)", front))
    score = clamp(10 - dump * 2 - long_paragraphs * 2 - max(0, names - 2), 0, 10)
    return int(score), f"设定倾倒 {dump} / 长段 {long_paragraphs} / 点名 {names}"


def chapter_end_hook(text: str) -> tuple[int, str]:
    tail = text[-T.CHAPTER_END_TAIL_CHARS:].strip()
    if not tail:
        return 0, "空章尾"
    if re.search(r"(第[零一二三四五六七八九十百千万\d]+章完|全书完)\s*[。！？!?]?\s*$", tail):
        return 0, "以「第X章完」收尾"
    if re.search(r"[？！!?]\s*$", tail):
        return 2, "反问/感叹收尾"
    if count_hits(tail, CHANGE_WORDS) or "……" in tail or "——" in tail:
        return 5, "留了未完成感"
    return 3, "平收，缺少钩子"


def module_g(ch1: str) -> tuple[int, str]:
    lengths = paragraph_lengths(ch1)
    variance = 0
    if len(lengths) >= 3:
        mean = sum(lengths) / len(lengths)
        if mean > 0:
            variance = sum(abs(length - mean) for length in lengths) / len(lengths) / mean
    pacing = clamp(variance * 12, 0, 5)
    hook, hook_reason = chapter_end_hook(ch1)
    return int(clamp(pacing + hook, 0, 10)), f"段落落差 {variance:.2f} / 章尾：{hook_reason}"


def module_h(ch1: str) -> tuple[int, str]:
    chinese = max(1, len(re.findall(r"[一-鿿]", ch1)))
    ai_hits = count_hits(ch1, AI_WORDS)
    dash = ch1.count("——") / chinese * 1000
    colon = ch1.count("：") / chinese * 1000
    dialogue = ch1.count("\"") + ch1.count("“")
    score = 5 - min(2, ai_hits * 0.5) - (1 if dash > T.DASH_PER_1000_MAX else 0) - (1 if colon > T.COLON_PER_1000_MAX else 0)
    if dialogue == 0 and chinese > 500:
        score -= 1
    return int(clamp(score, 0, 5)), f"AI词 {ai_hits} / 破折号 {dash:.2f} / 冒号 {colon:.2f}"


def detect_low_retention(front: str, ch1: str, three: str) -> list[dict[str, str]]:
    flags: list[dict[str, str]] = []
    first = first_sentences(front, 2)
    if count_hits(front, INFO_DUMP_WORDS) >= 3:
        flags.append({"id": "worldbuilding_dump", "name": "世界观说明书", "evidence": "前 300 字设定词密集"})
    if count_hits(first, WEATHER_WORDS) and not count_hits(first, ACTION_WORDS):
        flags.append({"id": "weather_opening", "name": "天气与风景镜头", "evidence": "第一句从天气/景物开始"})
    if count_hits(front, DREAM_WORDS) >= 1:
        flags.append({"id": "dream_wake", "name": "梦醒开局", "evidence": "出现醒来/做梦/恍惚"})
    names = len(re.findall(r"[一-龥]{2,3}(?:说|道|问|答|笑|站|坐)", front))
    if names >= 5:
        flags.append({"id": "meeting_roster", "name": "会议点名册", "evidence": f"前 300 字出现 {names} 个带动作的名字"})
    if count_hits(front, PASSIVE_WORDS) >= 2 and count_hits(front, GOAL_WORDS) + count_hits(front, ACTION_WORDS) <= 1:
        flags.append({"id": "passive_protagonist", "name": "被动主角", "evidence": "被动词多，目标/动作少"})
    if count_hits(front, SUFFERING_WORDS) >= 4 and count_hits(front, RELEASE_WORDS) == 0:
        flags.append({"id": "suffering_stack", "name": "苦难堆叠", "evidence": "连续受挫，无还手"})
    if count_hits(front, MECHANISM_WORDS) and count_hits(front, COST_WORDS) == 0:
        flags.append({"id": "free_mechanism", "name": "无代价金手指", "evidence": "机制出现但没有代价词"})
    if count_hits(front, ["回忆", "想起", "三年前", "小时候"]) >= 2:
        flags.append({"id": "memory_flashback", "name": "回忆抢戏", "evidence": "开篇长段回溯"})
    if count_hits(front, CONFLICT_WORDS) and count_hits(front, COST_WORDS) == 0 and count_hits(front, ["\"", "“"]) == 0:
        flags.append({"id": "fake_conflict", "name": "伪冲突", "evidence": "有冲突词但无代价、无对话"})
    if count_hits(front, SELF_DISCOURAGE):
        flags.append({"id": "author_discouragement", "name": "作者自我劝退", "evidence": "出现慢热/请耐心类话术"})
    return flags


def analyze(path: Path) -> dict[str, Any]:
    raw = read_text(path)
    chapters = split_chapters(raw)
    ch1 = chapters[0]
    three = "\n\n".join(chapters[:3])
    front = ch1[:300]
    modules = {
        "A_type_hook": module_a(front),
        "B_protagonist": module_b(front),
        "C_conflict_cost": module_c(front),
        "D_situation_change": module_d(ch1),
        "E_mechanism": module_e(three),
        "F_information": module_f(front),
        "G_pacing_end": module_g(ch1),
        "H_language": module_h(ch1),
    }
    totals = {key: value[0] for key, value in modules.items()}
    total = sum(totals.values())
    grade = "S" if total >= 90 else "A" if total >= 80 else "B" if total >= T.OPENING_PASS else "C" if total >= 60 else "D"
    flags = detect_low_retention(front, ch1, three)
    return {
        "file": str(path),
        "chapters": len(chapters),
        "total": total,
        "grade": grade,
        "pass": total >= T.OPENING_PASS,
        "ready": total >= T.OPENING_READY,
        "modules": {key: {"score": value[0], "reason": value[1]} for key, value in modules.items()},
        "low_retention": flags,
        "word_count": len(re.findall(r"[一-鿿]", ch1)),
    }


def render_text(result: dict[str, Any]) -> str:
    lines = [
        f"开篇评分：{result['total']}/100（{result['grade']}）"
        f"{' ✅ 可进正文' if result['ready'] else ' ⚠️ 需重构' if not result['pass'] else ' 🟡 可继续打磨'}",
        "",
        "模块：",
    ]
    labels = {
        "A_type_hook": ("类型卖点前置", 15),
        "B_protagonist": ("主角可跟随", 15),
        "C_conflict_cost": ("冲突与代价", 15),
        "D_situation_change": ("局面变化", 15),
        "E_mechanism": ("核心机制兑现", 15),
        "F_information": ("信息控制", 10),
        "G_pacing_end": ("节奏与章尾", 10),
        "H_language": ("语言与格式", 5),
    }
    for key, (label, max_score) in labels.items():
        item = result["modules"][key]
        lines.append(f"- {label}: {item['score']}/{max_score} — {item['reason']}")
    lines.extend(["", "低留存开篇："])
    if not result["low_retention"]:
        lines.append("- 未命中")
    for flag in result["low_retention"]:
        lines.append(f"- [{flag['id']}] {flag['name']}：{flag['evidence']}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="开篇 100 分卡与 12 类低留存检测")
    parser.add_argument("path", help="章节文件或包含前 3 章的目录")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--check", action="store_true", help="低于开篇通过线时返回 1")
    parser.add_argument("--min-score", type=int, default=T.OPENING_PASS)
    args = parser.parse_args()

    path = Path(args.path).expanduser()
    if path.is_dir():
        files = sorted(p for p in path.glob("*.md") if p.is_file())[:3]
        if not files:
            print(f"error: 目录下没有 md 文件: {path}", file=sys.stderr)
            return 2
        text = "\n\n".join(read_text(file) for file in files)
        raw = text
        chapters = split_chapters(raw)
        ch1 = chapters[0]
        three = "\n\n".join(chapters[:3])
        front = ch1[:300]
        modules = {
            "A_type_hook": module_a(front),
            "B_protagonist": module_b(front),
            "C_conflict_cost": module_c(front),
            "D_situation_change": module_d(ch1),
            "E_mechanism": module_e(three),
            "F_information": module_f(front),
            "G_pacing_end": module_g(ch1),
            "H_language": module_h(ch1),
        }
        total = sum(value[0] for value in modules.values())
        result = {
            "file": str(path),
            "chapters": len(chapters),
            "total": total,
            "grade": "S" if total >= 90 else "A" if total >= 80 else "B" if total >= T.OPENING_PASS else "C" if total >= 60 else "D",
            "pass": total >= args.min_score,
            "ready": total >= T.OPENING_READY,
            "modules": {key: {"score": value[0], "reason": value[1]} for key, value in modules.items()},
            "low_retention": detect_low_retention(front, ch1, three),
            "word_count": len(re.findall(r"[一-鿿]", ch1)),
        }
    else:
        result = analyze(path)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render_text(result))
    if args.check and not result["pass"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
