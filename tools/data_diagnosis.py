#!/usr/bin/env python3
"""Post-launch data diagnosis for serialized web novels.

Reads the 11 required metrics from JSON or Markdown, determines the current
stage, lists symptoms and prescriptions, and orders the seven-day actions by
"fix the front of the funnel first".
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

LABELS = {
    "words": ("总字数", "字数", "words"),
    "current_readers": ("当前在读", "在读", "current_readers"),
    "shelf_ratio": ("书架比", "shelf_ratio"),
    "follow_ratio": ("追更比", "follow_ratio"),
    "ch10_completion": ("前10章完读", "前10章完读率", "ch10_completion"),
    "wan_completion": ("10万字完读", "10万字完读率", "wan_completion"),
    "follow7": ("7日追更", "7日追更率", "follow7"),
    "daily_words": ("日均更新", "日均更新字数", "daily_words"),
    "gap_days": ("断更天数", "断更", "gap_days"),
    "score": ("作品评分", "评分", "score"),
    "click_rate": ("点击率", "曝光量", "click_rate"),
    "income": ("听读收益", "收益", "income"),
}

PRIORITY = [
    "断更",
    "日均更新不足",
    "冷启动",
    "书架比极差",
    "书架比警戒",
    "前 10 章完读率低于",
    "10 万字完读率不足",
    "追更率不足",
    "作品评分低于",
    "听读收益",
]


def stage_of(words: int) -> tuple[str, str]:
    if words < 80_000:
        return "L1", "签约 / 首章留存"
    if words < 100_000:
        return "L2", "验证期指标（书架比 / 追更比）"
    if words < 200_000:
        return "L3", "首秀池表现（完读率）"
    if words < 500_000:
        return "L4", "书测与中期留存"
    if words < 1_000_000:
        return "L5", "长线追更与收益结构"
    return "L6", "完本规划与 IP"


def _number(value: str) -> float | None:
    match = re.search(r"-?\d+(?:\.\d+)?", value.replace(",", ""))
    if not match:
        return None
    number = float(match.group())
    if "百万" in value:
        return number * 1_000_000
    if "万" in value:
        return number * 10_000
    if "千" in value:
        return number * 1_000
    return number


def _ratio(value: str) -> float | None:
    if ":" in value:
        parts = re.findall(r"\d+(?:\.\d+)?", value)
        if len(parts) >= 2:
            try:
                return float(parts[-1]) / max(1.0, float(parts[0]))
            except ZeroDivisionError:
                return None
    return _number(value)


def parse_markdown(text: str) -> dict[str, float]:
    data: dict[str, float] = {}
    for key, labels in LABELS.items():
        for label in labels:
            match = re.search(rf"{re.escape(label)}\s*[:：]?\s*([^\n|]+)", text)
            if not match:
                continue
            raw = match.group(1).strip()
            value = _ratio(raw) if key in {"shelf_ratio", "follow_ratio"} else _number(raw)
            if value is not None:
                data[key] = value
                break
    return data


def parse_input(path: Path) -> dict[str, float]:
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() == ".json":
        payload = json.loads(text)
        if not isinstance(payload, dict):
            raise ValueError("JSON 输入必须是对象")
        data: dict[str, float] = {}
        for key in LABELS:
            value = payload.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                data[key] = float(value)
            elif isinstance(value, str):
                parsed = _ratio(value) if key in {"shelf_ratio", "follow_ratio"} else _number(value)
                if parsed is not None:
                    data[key] = parsed
        return data
    return parse_markdown(text)


def diagnose(data: dict[str, float]) -> dict[str, Any]:
    words = int(data.get("words", 0) or 0)
    stage, stage_kpi = stage_of(words)
    issues: list[dict[str, Any]] = []
    causes: list[dict[str, Any]] = []
    actions: list[str] = []
    warnings: list[str] = []

    def add(metric: str, actual: str, target: str, severity: str, cause: str, fix: str, action: str = "") -> None:
        issues.append({"metric": metric, "actual": actual, "target": target, "severity": severity})
        causes.append({"cause": cause, "fix": fix})
        if action:
            actions.append(action)

    gap = data.get("gap_days", 0)
    if gap >= 3:
        add("断更天数", f"{gap:g} 天", "0 天", "严重",
            "断更 ≥3 天 —— 平台对连载稳定性权重极高，流量会断崖式下跌",
            "立刻恢复日更，固定时段，提前储备 3-7 天存稿",
            "今天恢复更新，并写出未来 3 天存稿")
    elif gap in (1, 2):
        add("断更天数", f"{gap:g} 天", "0 天", "警告",
            "存在断更 —— 验证期任意一天断更会终止本次验证",
            "固定更新时段，储备存稿",
            "恢复日更并建立 3 天存稿缓冲")

    daily = data.get("daily_words", 0)
    need = T.DATA_THRESHOLDS["daily_words_show"] if words >= 100_000 else T.DATA_THRESHOLDS["daily_words"]
    if daily and daily < need:
        add("日均更新字数", f"{daily:g} 字", f"≥{need} 字", "严重",
            "日均更新不足 —— 验证期要求稳定日更",
            f"把日更提到 {need} 字，拆成 2-3 章发布，单章不低于 1000 字",
            f"把日更稳定到 {need} 字以上")

    if words < 80_000:
        causes.append({
            "cause": "冷启动期只测点击率，不考核长留存",
            "fix": "书名带赛道热词；封面主体清晰；简介用「人物 + 变化 + 代价」句式",
        })
        actions.append("自检书名/封面/简介：书名最醒目的词，前三章是否真的出现")

    shelf = data.get("shelf_ratio")
    if shelf is not None:
        if shelf > T.DATA_THRESHOLDS["shelf_warn"]:
            add("书架比", f"1:{shelf:.1f}", "≤1:10", "严重",
                "书架比极差 —— 开篇承诺与正文不符，读者存了不看",
                "统一书名/简介与前三章承诺；强化第一章局面变化；重写前 300 字")
        elif shelf > T.DATA_THRESHOLDS["shelf_pass"]:
            add("书架比", f"1:{shelf:.1f}", "≤1:10", "警告",
                "书架比警戒 —— 加入书架没有转化为持续阅读",
                "前 10 章补足章末钩子与情绪回报；砍掉无推进过渡段",
                "重排未来 10 章细纲，每章补一个章尾钩子")
        elif shelf <= T.DATA_THRESHOLDS["shelf_excellent"]:
            causes.append({"cause": f"书架比优秀（1:{shelf:.1f}）✓", "fix": "保持门面，按计划推进书测与长线加码"})

    ch10 = data.get("ch10_completion")
    if ch10 is not None:
        if ch10 < T.DATA_THRESHOLDS["ch10_completion"]:
            add("前 10 章完读率", f"{ch10:.1f}%", f"≥{T.DATA_THRESHOLDS['ch10_completion']}%", "严重",
                "前 10 章完读率低于腰斩线 —— 开篇与章节钩子系统性不足",
                "用开篇 100 分卡重构前三章；前 10 章逐章补章尾钩子",
                "对前 3 章做结构重写；第 4-10 章逐章补章尾钩子")
        elif ch10 < 15:
            add("前 10 章完读率", f"{ch10:.1f}%", "≥15%", "警告",
                "前 10 章完读率偏低 —— 开篇承诺兑现不够",
                "前三章至少给一次完整小兑现，章末留未完成感")

    wan = data.get("wan_completion")
    if wan is not None and wan < T.DATA_THRESHOLDS["wan_completion"]:
        add("10 万字完读率", f"{wan:.1f}%", f"≥{T.DATA_THRESHOLDS['wan_completion']}%", "警告",
            "10 万字完读率不足 —— 中段注水 / 核心机制未运转 / 主线迟迟不立",
            "砍过渡章，提前第一阶段闭环，每 2 章一次小爽点",
            "定位完读率断崖的章节区段，重写该区段的事件密度")

    follow7 = data.get("follow7")
    if follow7 is not None and follow7 < T.DATA_THRESHOLDS["follow7"]:
        add("7 日追更率", f"{follow7:.1f}%", f"≥{T.DATA_THRESHOLDS['follow7']}%", "警告",
            "追更率不足 —— 更新不稳定 / 章末钩子同质化 / 情绪回报不足",
            "固定更新时段；章尾四写法轮换；每 2 章一次小爽点",
            "检查最近 10 章章尾钩子类型，是否连续同类型")

    score = data.get("score")
    if score is not None and score < T.DATA_THRESHOLDS["score"]:
        add("作品评分", f"{score:.1f}", f"≥{T.DATA_THRESHOLDS['score']}", "警告",
            "评分低于及格线 —— 结构性问题已反映到读者打分",
            "做一次 16 维体检，重点修人设一致性与逻辑漏洞",
            "列出读者最可能挑的前 5 个问题")

    income = data.get("income")
    if income is not None and income < T.DATA_THRESHOLDS["income"]:
        causes.append({
            "cause": f"听读收益 {income:.0f} 元，低于激励门槛",
            "fix": "先修完读率再冲字数档位；先堆字数后修质量等于把钱堆在漏桶里",
        })

    def rank(item: dict[str, Any]) -> int:
        text = item["cause"]
        for index, key in enumerate(PRIORITY):
            if key in text:
                return index
        return len(PRIORITY)

    causes.sort(key=rank)
    for index, item in enumerate(causes, 1):
        item["priority"] = index

    return {
        "schema_version": "1.0",
        "stage": stage,
        "stage_kpi": stage_kpi,
        "words": words,
        "issues": issues,
        "causes": causes,
        "actions": actions,
        "warnings": warnings,
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        f"# 数据诊断 · {result['stage']}",
        "",
        f"- 当前字数：{result['words']}",
        f"- 阶段考核：{result['stage_kpi']}",
        "",
        "## 问题",
    ]
    if not result["issues"]:
        lines.append("- 未发现明显指标问题")
    for issue in result["issues"]:
        lines.append(
            f"- [{issue['severity']}] {issue['metric']}：实测 {issue['actual']}，目标 {issue['target']}"
        )
    lines.extend(["", "## 处方（先修最前端）"])
    for item in result["causes"]:
        lines.append(f"{item['priority']}. **{item['cause']}**")
        lines.append(f"   - 处方：{item['fix']}")
    lines.extend(["", "## 七天动作"])
    if not result["actions"]:
        lines.append("- 保持当前更新与节奏")
    for action in result["actions"]:
        lines.append(f"- {action}")
    lines.extend(
        [
            "",
            "> 七天里只动一件事，动三件就测不出因果。数据引用必须带时间、单位、样本、口径和比较对象。",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="上线后 11 项数据诊断")
    parser.add_argument("--input", required=True, help="数据 JSON 或 Markdown")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", default="", help="Markdown 报告输出路径")
    args = parser.parse_args()

    path = Path(args.input).expanduser()
    try:
        data = parse_input(path)
        if not data:
            raise ValueError("未解析到任何指标；请至少提供总字数")
        result = diagnose(data)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.output:
        output = Path(args.output).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(render_markdown(result), encoding="utf-8")
        print(f"[OK] 诊断报告: {output}")
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif not args.output:
        print(render_markdown(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
