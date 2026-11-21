#!/usr/bin/env python3
"""从用户提供的文本建立可续写项目。

流程：
1. 拆文（角色/剧情/世界观/风格）
2. 初始化标准项目结构
3. 把拆文结果导入真相文件（标记为推断）
4. 生成设定、结构、细纲和导入报告
5. 等待用户审查后运行 ``project_bootstrap_pipeline.py continuation-gate --approve``

本脚本不会直接解锁正文；``can_write_chapter`` 只由 continuation-gate 写入。
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPTS_DIR.parents[1]
for entry in (PROJECT_ROOT, SCRIPTS_DIR):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from pipeline_utils import load_json, now_iso, rel, save_json  # noqa: E402
from novel_creation_promax.core.roots import workspace_root  # noqa: E402
from novel_creation_promax.core.workspace_confirmation import (  # noqa: E402
    WorkspaceConfirmationError,
    confirm,
    require_confirmed,
)

BOOTSTRAP = SCRIPTS_DIR / "project_bootstrap_pipeline.py"
TRUTH = SCRIPTS_DIR / "story_truth_manager.py"
DECONSTRUCT = SCRIPTS_DIR / "deconstruct_novel.py"
STYLE_DNA = PROJECT_ROOT / "skills" / "novel-memory" / "scripts" / "style_dna_extractor.py"


def run(cmd: list[str], cwd: Path, label: str) -> subprocess.CompletedProcess:
    print(f"[RUN] {label}")
    result = subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = (result.stdout or "") + (result.stderr or "")
    if output.strip():
        print(output.strip())
    return result


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def name_of(item: Any) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        return str(item.get("name") or item.get("title") or "").strip()
    return ""


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def render_characters(characters: dict[str, Any]) -> str:
    items = [item for item in characters.get("characters", []) if isinstance(item, dict)]
    lines = [
        "# 人物档案（续写导入）",
        "",
        "> 来源：用户提供的原文拆文结果。以下身份、收入、居所等字段均为原文未说明，",
        "> 续写前必须回读原文补全；未补全前不得凭空新增设定。",
        "",
        "## 角色总表",
        "",
        "| 角色 | 出现次数 | 定位 |",
        "|---|---:|---|",
    ]
    for item in items:
        lines.append(f"| {name_of(item)} | {safe_int(item.get('count'))} | 续写导入角色（拆文推断） |")
    attribution = characters.get("dialogue_attribution")
    if isinstance(attribution, dict) and attribution:
        lines.extend(["", "## 对话样本", ""])
        for name, samples in attribution.items():
            if not isinstance(samples, list) or not samples:
                continue
            lines.append(f"### {name}")
            for sample in samples[:3]:
                lines.append(f"- {sample}")
            lines.append("")
    lines.extend(
        [
            "## 续写前必须补全",
            "",
            "- 年龄、职业、收入、居所、学历/技能",
            "- 外在目标、真实欲望、核心恐惧、底线",
            "- 说话句长、口头禅、专业词、禁用词",
            "- 压力反应、决策方式、不能做的事",
            "",
        ]
    )
    return "\n".join(lines)


def render_entities(title: str, items: list[Any], kind: str) -> str:
    lines = [f"# {title}", "", "> 来源：拆文推断。原文未说明的字段必须在续写前补全。", "", f"## {kind}总表", "", "| 名称 | 出现次数 |", "|---|---:|"]
    for item in items:
        lines.append(f"| {name_of(item)} | {safe_int(item.get('count')) if isinstance(item, dict) else 0} |")
    if not items:
        lines.append("| 原文未提取到 | 0 |")
    lines.extend(["", "## 使用边界", "", "- 只写原文出现过或可合理推断的实体。", "- 新增实体必须先补设定，不得在正文里临时发明。", ""])
    return "\n".join(lines)


def render_events(plot: dict[str, Any]) -> str:
    chapters = [item for item in plot.get("chapters", []) if isinstance(item, dict)]
    lines = [
        "# 事件档案（续写导入）",
        "",
        "> 来源：拆文章节统计与转折点。续写必须承接最后一章的结尾状态。",
        "",
        "## 章节节点",
        "",
        "| 章 | 字数 | 对话占比 | 情绪 | 句均长 |",
        "|---:|---:|---:|---|---:|",
    ]
    for item in chapters[-20:]:
        emotions = item.get("emotions") if isinstance(item.get("emotions"), dict) else {}
        emotion_text = "、".join(f"{key}:{value}" for key, value in emotions.items()) or "未识别"
        lines.append(
            f"| {safe_int(item.get('chapter_num'))} | {safe_int(item.get('char_count'))} | "
            f"{float(item.get('dialogue_ratio', 0) or 0):.0%} | {emotion_text} | "
            f"{float(item.get('avg_sentence_length', 0) or 0):.1f} |"
        )
    turning_points = [item for item in plot.get("turning_points", []) if isinstance(item, dict)]
    if turning_points:
        lines.extend(["", "## 转折点", ""])
        for item in turning_points:
            lines.append(f"- 第{safe_int(item.get('chapter_num'))}章：{name_of(item) or '转折点'}")
    lines.append("")
    return "\n".join(lines)


def render_relationships(characters: dict[str, Any]) -> str:
    relationships = [item for item in characters.get("relationships", []) if isinstance(item, dict)]
    lines = [
        "# 关系网络（续写导入）",
        "",
        "> 来源：角色共现分析。共现只说明“同场出现”，不代表关系性质；",
        "> 关系类型、信任度和信息差必须在续写前按原文补全。",
        "",
        "| 角色 A | 角色 B | 共现次数 | 强度 | 关系性质 |",
        "|---|---|---:|---|---|",
    ]
    for item in relationships:
        pair = item.get("characters") if isinstance(item.get("characters"), list) else []
        if len(pair) != 2:
            continue
        lines.append(
            f"| {pair[0]} | {pair[1]} | {safe_int(item.get('co_occurrence_count'))} | "
            f"{item.get('strength', '')} | 原文未说明 |"
        )
    if len(lines) == 8:
        lines.append("| 原文未提取到 | - | 0 | - | - |")
    lines.append("")
    return "\n".join(lines)


def render_constraints(style: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# 常识约束（续写导入）",
            "",
            "> 来源：拆文风格与世界要素。以下为统计特征，不是作者确认的设定。",
            "",
            "## 已知风格特征",
            "",
            f"- 平均句长：{float(style.get('avg_sentence_length', 0) or 0):.1f}",
            f"- 句长标准差：{float(style.get('sentence_length_std', 0) or 0):.1f}",
            f"- 对话占比：{float(style.get('dialogue_ratio', 0) or 0):.0%}",
            f"- 词汇丰富度：{float(style.get('vocabulary_richness', 0) or 0):.2f}",
            "",
            "## 续写硬约束",
            "",
            "- 原文未说明的世界规则不得补成硬设定。",
            "- 角色能力、身份、资源不得突然升级。",
            "- 时间线、地点、人物称呼以原文最后一次出现为准。",
            "- 风格 DNA 见 `记忆/style_dna_baseline.json`；漂移时先校准再改剧情。",
            "",
        ]
    )


def render_structure(plot: dict[str, Any]) -> str:
    chapters = [item for item in plot.get("chapters", []) if isinstance(item, dict)]
    lines = [
        "# 主线结构（续写导入）",
        "",
        "> 来源：拆文章节统计。主线、支线和伏笔仍需用户确认。",
        "",
        "## 已知章节",
        "",
    ]
    for item in chapters:
        lines.append(
            f"- 第{safe_int(item.get('chapter_num'))}章：{safe_int(item.get('char_count'))} 字，"
            f"对话占比 {float(item.get('dialogue_ratio', 0) or 0):.0%}"
        )
    lines.extend(
        [
            "",
            "## 待确认",
            "",
            "- 主线目标与最终对手",
            "- 支线清单与回收计划",
            "- 已埋伏笔与预计回收章节",
            "- 下一卷/下一阶段的冲突升级点",
            "",
        ]
    )
    return "\n".join(lines)


def render_outline(title: str, source: Path, summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {title} · 续写总纲（导入）",
            "",
            f"> 来源：`{source}`",
            f"> 拆文章节：{summary['chapters']} · 角色：{summary['characters']} · "
            f"地点：{summary['locations']} · 势力：{summary['factions']} · 关系：{summary['relationships']}",
            "",
            "## 已知",
            "",
            "- 原文已发生的章节事件与角色共现关系已导入真相文件。",
            "- 风格 DNA 已写入记忆。",
            "",
            "## 未知（续写前必须确认）",
            "",
            "- 主线终点、卷结构、伏笔回收计划",
            "- 角色动机、能力边界、收入与居所逻辑",
            "- 平台、目标字数与更新节奏",
            "",
            "## 下一步",
            "",
            "1. 审查 `素材/continuation_import_report.md`。",
            "2. 补齐 `设定/` 与 `细纲/续写细纲.md`。",
            "3. 运行 `project_bootstrap_pipeline.py continuation-gate --approve`。",
            "4. 写第 1 章（续写章）。",
            "",
        ]
    )


def render_chapter_outline(plot: dict[str, Any]) -> str:
    chapters = [item for item in plot.get("chapters", []) if isinstance(item, dict)]
    last = chapters[-1] if chapters else {}
    last_no = safe_int(last.get("chapter_num"))
    next_no = last_no + 1
    return "\n".join(
        [
            "# 续写细纲",
            "",
            f"> 原文最后已知章节：第{last_no}章" if last_no else "> 原文未识别到章节号",
            "",
            "## 上一章结尾状态",
            "",
            "- 地点：需回读原文确认",
            "- 在场人物：需回读原文确认",
            "- 未解决冲突：需回读原文确认",
            "",
            f"## 第{next_no}章 待填写",
            "",
            "- 本章目标：",
            "- 核心冲突：",
            "- 爽点/情绪峰值：",
            "- 伏笔推进：",
            "- 章末截断点：",
            "",
            "> 细纲必须由作者或 Claude 回读原文后补齐，不得用拆文统计直接充当细纲。",
            "",
        ]
    )


def render_report_markdown(report: dict[str, Any]) -> str:
    source = report["source"]
    lines = [
        "# 续写导入报告",
        "",
        f"> 生成时间：{report['generated_at']}",
        f"> 原文：`{source['input']}`",
        f"> 拆文目录：`{source['deconstruct_dir']}`",
        "",
        "## 统计",
        "",
        f"- 章节：{source['chapters']}",
        f"- 角色：{source['characters']}",
        f"- 地点：{source['locations']}",
        f"- 势力：{source['factions']}",
        f"- 关系：{source['relationships']}",
        "",
        "## 缺口",
        "",
    ]
    gaps = report.get("gaps") or []
    lines.extend(f"- {item}" for item in gaps) if gaps else lines.append("- 无结构性缺口")
    lines.extend(
        [
            "",
            "## 重要说明",
            "",
            "- 真相文件中的记录均为 `source=deconstruction_import`，表示“从原文推断”，不是作者确认的事实。",
            "- 拆文不能替代细纲、动机和能力边界；续写前必须回读原文补全。",
            "- 未通过 `continuation-gate --approve` 前，正文写作门禁保持关闭。",
            "",
            "## 下一步",
            "",
            "1. 逐项审查本报告与 `设定/` 下的导入内容。",
            "2. 补齐 `细纲/续写细纲.md`。",
            "3. 确认后运行：",
            "",
            "```bash",
            f'python3 novel_creation_promax/scripts/project_bootstrap_pipeline.py continuation-gate \\',
            f'  --novel-dir "{report["project"]["novel_dir"]}" --approve',
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="从用户文本建立可续写项目")
    parser.add_argument("--input", required=True, help="原文文件或章节目录")
    parser.add_argument("--title", required=True)
    parser.add_argument("--platform", default="番茄")
    parser.add_argument("--genre", default="")
    parser.add_argument("--author", default="")
    parser.add_argument("--novel-dir", default="")
    parser.add_argument("--deconstruct-dir", default="", help="复用已有拆文输出")
    parser.add_argument("--skip-deconstruct", action="store_true")
    parser.add_argument("--confirm-workspace", action="store_true")
    parser.add_argument("--approve", action="store_true", help="报告已审查，直接写入续写门禁")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    workspace = workspace_root().resolve()
    try:
        if args.confirm_workspace:
            confirm(workspace, by="cli")
        require_confirmed(workspace)
    except WorkspaceConfirmationError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    source = Path(args.input).expanduser().resolve()
    if not source.exists():
        print(f"[ERROR] 原文不存在: {source}", file=sys.stderr)
        return 1

    novel_dir = (
        Path(args.novel_dir).expanduser().resolve()
        if args.novel_dir
        else workspace / "novel_output" / args.platform / args.title
    )
    if novel_dir.exists() and not args.force:
        print(f"[ERROR] 项目已存在: {novel_dir}；用 --force 重新导入", file=sys.stderr)
        return 1

    deconstruct_dir = (
        Path(args.deconstruct_dir).expanduser().resolve()
        if args.deconstruct_dir
        else workspace / "素材" / "拆文" / args.title
    )
    if not args.skip_deconstruct:
        result = run(
            [
                sys.executable,
                str(DECONSTRUCT),
                "--input",
                str(source),
                "--output",
                str(deconstruct_dir),
                "--skip-llm-prompts",
            ],
            workspace,
            "拆文",
        )
        if result.returncode != 0:
            return 1
    elif not (deconstruct_dir / "characters.json").is_file():
        print(f"[ERROR] 拆文目录缺少 characters.json: {deconstruct_dir}", file=sys.stderr)
        return 1

    init_cmd = [
        sys.executable,
        str(BOOTSTRAP),
        "init",
        "--platform",
        args.platform,
        "--title",
        args.title,
        "--genre",
        args.genre,
        "--premise",
        f"续写导入：基于用户提供的原文（{source.name}）",
        "--confirm-workspace",
    ]
    if args.novel_dir:
        init_cmd.extend(["--novel-dir", str(novel_dir)])
    if args.force:
        init_cmd.append("--force")
    result = run(init_cmd, workspace, "初始化项目")
    if result.returncode != 0:
        return 1

    # init 会生成长篇八卷占位细纲；续写项目只保留续写细纲。
    for volume in sorted((novel_dir / "细纲").glob("卷*.md")):
        try:
            if "待填写" in volume.read_text(encoding="utf-8"):
                volume.unlink()
        except OSError:
            continue
    write_text(
        novel_dir / "创意" / "创意方案.md",
        "\n".join(
            [
                f"# {args.title} · 续写导入",
                "",
                f"- 平台：{args.platform}",
                f"- 题材：{args.genre or '原文未说明'}",
                f"- 来源：用户提供的原文 `{source.name}`",
                "- 说明：本项目不是从零立项，没有调研与原创创意阶段；",
                "  角色、世界观和风格来自拆文推断，必须经用户审查。",
                "",
            ]
        ),
    )

    result = run(
        [
            sys.executable,
            str(TRUTH),
            "import-deconstruction",
            "--novel-dir",
            str(novel_dir),
            "--input",
            str(deconstruct_dir),
            "--apply",
        ],
        workspace,
        "导入真相文件",
    )
    if result.returncode != 0:
        return 1

    baseline = novel_dir / "记忆" / "style_dna_baseline.json"
    style_result = run(
        [
            sys.executable,
            str(STYLE_DNA),
            "--input",
            str(source),
            "--output",
            str(baseline),
            "--author",
            args.author,
        ],
        workspace,
        "提取风格 DNA",
    )
    if style_result.returncode == 0 and baseline.is_file():
        shutil.copyfile(baseline, novel_dir / "记忆" / "style_dna.json")
    else:
        print("[WARN] 风格 DNA 提取失败；续写前可手动补充 style_dna_baseline.json", file=sys.stderr)

    characters = load_json(deconstruct_dir / "characters.json", {})
    world = load_json(deconstruct_dir / "world_settings.json", {})
    plot = load_json(deconstruct_dir / "plot_structure.json", {})
    style = load_json(deconstruct_dir / "style_profile.json", {})
    for payload in (characters, world, plot, style):
        if not isinstance(payload, dict):
            print("[ERROR] 拆文输出格式无效", file=sys.stderr)
            return 1

    locations = [item for item in world.get("locations", []) if name_of(item)]
    factions = [item for item in world.get("factions", []) if name_of(item)]
    relationships = [item for item in characters.get("relationships", []) if isinstance(item, dict)]
    plot_chapters = [item for item in plot.get("chapters", []) if isinstance(item, dict)]
    summary = {
        "chapters": len(plot_chapters),
        "last_chapter": max(
            (safe_int(item.get("chapter_num")) for item in plot_chapters),
            default=0,
        ),
        "characters": len([item for item in characters.get("characters", []) if isinstance(item, dict)]),
        "locations": len(locations),
        "factions": len(factions),
        "relationships": len(relationships),
    }

    write_text(novel_dir / "设定" / "人物档案.md", render_characters(characters))
    write_text(novel_dir / "设定" / "地点档案.md", render_entities("地点档案（续写导入）", locations, "地点"))
    write_text(novel_dir / "设定" / "势力档案.md", render_entities("势力档案（续写导入）", factions, "势力"))
    write_text(novel_dir / "设定" / "事件档案.md", render_events(plot))
    write_text(novel_dir / "设定" / "关系网络.md", render_relationships(characters))
    write_text(novel_dir / "设定" / "常识约束.md", render_constraints(style))
    write_text(
        novel_dir / "设定" / "世界观与人物.md",
        "\n".join(
            [
                f"# {args.title} · 设定（续写导入）",
                "",
                "> 详细内容见人物档案、地点档案、势力档案、事件档案、关系网络和常识约束。",
                "",
                "## 世界观",
                "",
                "原文未说明；续写前必须补全时代、地点、规则与能力边界。",
                "",
                "## 人物体系",
                "",
                "见人物档案。所有身份与动机字段均需回读原文补全。",
                "",
                "## 地点/势力/事件",
                "",
                "见对应档案。拆文统计只能作为索引，不能替代设定。",
                "",
            ]
        ),
    )
    write_text(novel_dir / "结构" / "主线结构.md", render_structure(plot))
    write_text(novel_dir / "outline.md", render_outline(args.title, source, summary))
    write_text(novel_dir / "细纲" / "续写细纲.md", render_chapter_outline(plot))

    gaps = []
    if summary["locations"] == 0:
        gaps.append("原文未提取到地点；需回读原文补全地点档案")
    if summary["factions"] == 0:
        gaps.append("原文未提取到势力；需回读原文补全势力档案")
    if summary["relationships"] == 0:
        gaps.append("原文未提取到角色关系；需回读原文补全关系网络")
    gaps.append("主线、支线、伏笔与角色动机需人工确认")

    report = {
        "schema_version": "1.0",
        "mode": "continuation_import",
        "generated_at": now_iso(),
        "source": {
            "input": str(source),
            "deconstruct_dir": str(deconstruct_dir),
            **summary,
        },
        "project": {
            "title": args.title,
            "platform": args.platform,
            "genre": args.genre,
            "novel_dir": rel(novel_dir, workspace),
        },
        "review_status": "reviewed" if args.approve else "pending",
        "gaps": gaps,
        "next_steps": [
            "审查 continuation_import_report.md",
            "补齐设定与续写细纲",
            "continuation-gate --approve 解锁正文",
        ],
    }
    save_json(novel_dir / "素材" / "continuation_import_report.json", report)
    write_text(novel_dir / "素材" / "continuation_import_report.md", render_report_markdown(report))

    state_path = novel_dir / "novel_state.json"
    state = load_json(state_path, {})
    if isinstance(state, dict):
        state["import_mode"] = "continuation"
        state["import_last_chapter"] = int(summary.get("last_chapter", 0) or 0)
        state["updated_at"] = now_iso()
        save_json(state_path, state)

    validate = run(
        [
            sys.executable,
            str(TRUTH),
            "validate",
            "--novel-dir",
            str(novel_dir),
            "--continuation",
        ],
        workspace,
        "校验导入后的真相文件",
    )
    if validate.returncode != 0:
        print("[WARN] 真相文件校验未通过；先修复再运行 continuation-gate", file=sys.stderr)

    if args.approve:
        result = run(
            [
                sys.executable,
                str(BOOTSTRAP),
                "continuation-gate",
                "--novel-dir",
                str(novel_dir),
                "--approve",
            ],
            workspace,
            "写入续写门禁",
        )
        if result.returncode != 0:
            return 1
    else:
        print("[NEXT] 审查报告后运行：")
        print(
            f'  python3 novel_creation_promax/scripts/project_bootstrap_pipeline.py continuation-gate \\\n'
            f'    --novel-dir "{novel_dir}" --approve'
        )

    print(f"[OK] 续写项目已建立: {novel_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
