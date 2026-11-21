#!/usr/bin/env python3
"""
写作流水线

把章节写作的确定性门禁收束到一个入口：
pre  = 章节前检查 + 记忆包
post = gate + 写后审计 + 风格/OOC可选检查 + chapter passport
all  = pre + post（适合章节文件已存在时）
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from pipeline_utils import (
    count_chinese_chars,
    find_chapter_file,
    load_json,
    load_passport,
    now_iso,
    passport_path,
    rel,
    save_json,
    save_passport,
    update_novel_state,
)


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from novel_creation_promax.core.audit_schema import find_audit_report, load_audit, load_audit_all
from novel_creation_promax.core.chapter_commit import (
    commit_id_for,
    commit_path as chapter_commit_path,
    remove_chapter_commit,
    record_chapter_commit,
)
from novel_creation_promax.core.chapter_workflow import chapter_lock, transition
from novel_creation_promax.core.contracts import save_contract_report, validate_chapter_contracts
from novel_creation_promax.core.dashboard import write_dashboards
from novel_creation_promax.core.gate import verify_bootstrap_gate
from novel_creation_promax.core.knowledge_routes import build_and_save_chapter_pack
from novel_creation_promax.core.passport import previous_chapter_audited
from novel_creation_promax.core.paths import find_memory_dir
from novel_creation_promax.core.run_ledger import record_subprocess
from novel_creation_promax.core.scene_passport import initialize_scene_plan
from novel_creation_promax.core.quality_profiles import QUALITY_MODES, quality_profile, quality_review_path
from novel_creation_promax.core.review_result import review_gate, review_path as chapter_review_path
from novel_creation_promax.core.revision_control import ensure_current_revision
from novel_creation_promax.core.roots import workspace_root
from novel_creation_promax.core.tension_curve import load_tension_contract, validate_chapter_tension
from novel_creation_promax.core import workspace_confirmation as wc

SCRIPTS_DIR = PROJECT_ROOT / "novel_creation_promax" / "scripts"
MEMORY_SCRIPTS_DIR = PROJECT_ROOT / "skills" / "novel-memory" / "scripts"
MEMORY_SCRIPT = MEMORY_SCRIPTS_DIR / "memory_manager.py"
TRUTH_SCRIPT = SCRIPTS_DIR / "story_truth_manager.py"
PASS_THRESHOLD = 70
POST_PHASES = ("audit", "truth", "quality", "memory", "commit")


def resolve_path(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else workspace_root() / p


def ensure_bootstrap_gate(novel_dir: Path) -> bool:
    ok, detail = verify_bootstrap_gate(novel_dir)
    if ok:
        print(f"[OK] {detail}")
        return True

    print("[BLOCKED] 新书立项门禁未通过，禁止进入正文写作流水线。", file=sys.stderr)
    print(f"[REASON] {detail}", file=sys.stderr)
    print(
        "[NEXT] 先运行: python novel_creation_promax/scripts/project_bootstrap_pipeline.py "
        f"seal --novel-dir \"{novel_dir}\"",
        file=sys.stderr,
    )
    return False


def record_override_debt(novel_dir: Path, chapter: int, stage: str, reason: str) -> None:
    """把跳过门禁的行为写进 novel_state.override_debt，禁止静默绕过。"""
    state_path = novel_dir / "novel_state.json"
    state = load_json(state_path, {})
    if not isinstance(state, dict):
        state = {}
    debts = state.get("override_debt")
    if not isinstance(debts, list):
        debts = []
        state["override_debt"] = debts
    debts.append(
        {
            "chapter": chapter,
            "stage": stage,
            "reason": reason,
            "at": now_iso(),
            "resolved": False,
        }
    )
    state["updated_at"] = now_iso()
    save_json(state_path, state)


def ensure_prev_chapter_audited(
    novel_dir: Path,
    chapter: int,
    *,
    allow_override: bool = False,
    stage: str = "pre",
    override_reason: str = "",
) -> bool:
    """前置审计门禁：写第 N 章前，第 N-1 章必须已跑过 post_write_audit 并 pass。

    放行条件：
    1. chapter == 1（第一章无前置）
    2. 第 N-1 章 passport 或 novel_state 记录明确为 audit pass
    3. allow_override=True **且** 提供了 override_reason（会落 override_debt 留痕）
    """
    if chapter <= 1:
        return True

    state_path = novel_dir / "novel_state.json"
    state = load_json(state_path, {})
    if isinstance(state, dict) and state.get("import_mode") == "continuation":
        imported_last = int(state.get("import_last_chapter", 0) or 0)
        if imported_last and chapter == imported_last + 1:
            print(
                f"[OK] 续写导入：第{imported_last}章为外部原文，"
                "无本项目审计记录，跳过前置审计门禁"
            )
            return True

    # 先按正常规则判定；只有确实不通过时才走 override 分支
    ok, detail = previous_chapter_audited(novel_dir, chapter)
    if ok:
        print(f"[OK] {detail}")
        return True

    if allow_override:
        if not override_reason.strip():
            print(
                "[BLOCKED] --override-prev-audit 必须同时提供 --override-reason，禁止静默绕过门禁。",
                file=sys.stderr,
            )
            return False
        record_override_debt(novel_dir, chapter, stage, override_reason.strip())
        print(
            f"[WARN] {stage} 阶段跳过第{chapter-1}章审计门禁（{detail}），已记录 override_debt: {override_reason}",
            file=sys.stderr,
        )
        return True

    prev = chapter - 1

    print(
        f"[BLOCKED] {detail}，禁止写第{chapter}章。",
        file=sys.stderr,
    )
    print(
        "[NEXT] 先跑: python novel_creation_promax/scripts/write_pipeline.py post "
        f"--novel-dir \"{novel_dir}\" --chapter {prev}",
        file=sys.stderr,
    )
    print(
        "[BYPASS] 紧急情况可加 --override-prev-audit --override-reason \"原因\"（会落 override_debt）。",
        file=sys.stderr,
    )
    return False


def ensure_dirs(novel_dir: Path) -> None:
    for name in ["摘要", "素材"]:
        (novel_dir / name).mkdir(parents=True, exist_ok=True)
    # 已有 memory/ 的历史项目不再创建空的 记忆/，避免双目录
    find_memory_dir(novel_dir).mkdir(parents=True, exist_ok=True)


def save_workflow_checkpoint(
    novel_dir: Path,
    chapter: int,
    passport: dict[str, Any],
    *,
    stage: str,
    status: str,
    next_action: str,
    error: str = "",
) -> dict[str, Any]:
    """Persist passport and project index after every major phase."""
    passport["workflow"] = transition(
        passport.get("workflow", {}),
        stage,
        status,
        next_action=next_action,
        error=error,
    )
    save_passport(novel_dir, chapter, passport)
    update_novel_state(
        novel_dir,
        chapter=chapter,
        word_count=passport.get("word_count"),
        passport=rel(passport_path(novel_dir, chapter), novel_dir),
        workflow_update=passport["workflow"],
    )
    return passport["workflow"]


def ensure_truth_files(novel_dir: Path) -> bool:
    report_path = novel_dir / "素材" / "truth_files_gate.json"
    result = run_command(
        [
            sys.executable,
            str(TRUTH_SCRIPT),
            "validate",
            "--novel-dir",
            str(novel_dir),
            "--output",
            str(report_path),
        ],
        "真相文件校验",
    )
    return result["returncode"] == 0


def compile_truth_inputs(novel_dir: Path, chapter: int, title: str, passport: dict[str, Any]) -> bool:
    rule_stack = novel_dir / "摘要" / f"chapter_{chapter:03d}_rule_stack.json"
    truth_brief = novel_dir / "素材" / f"chapter_{chapter:03d}_truth_brief.md"
    result = run_command(
        [
            sys.executable,
            str(TRUTH_SCRIPT),
            "compile",
            "--novel-dir",
            str(novel_dir),
            "--chapter",
            str(chapter),
            "--title",
            title,
            "--output",
            str(rule_stack),
            "--brief-output",
            str(truth_brief),
        ],
        "编译章节真相约束",
    )
    passport["pipeline"]["truth_compile"] = result["status"]
    passport["inputs"]["rule_stack"] = rel(rule_stack, novel_dir)
    passport["inputs"]["truth_brief"] = rel(truth_brief, novel_dir)
    return result["returncode"] == 0


def create_truth_delta_template(novel_dir: Path, chapter: int, title: str, passport: dict[str, Any]) -> bool:
    result = run_command(
        [
            sys.executable,
            str(TRUTH_SCRIPT),
            "delta-template",
            "--novel-dir",
            str(novel_dir),
            "--chapter",
            str(chapter),
            "--title",
            title,
        ],
        "创建章节 truth delta 模板",
    )
    delta_file = novel_dir / "摘要" / f"chapter_{chapter:03d}_truth_delta.json"
    passport["pipeline"]["truth_delta_template"] = result["status"]
    passport["inputs"]["truth_delta"] = rel(delta_file, novel_dir)
    return result["returncode"] == 0


def build_and_save_knowledge_pack(
    novel_dir: Path,
    chapter: int,
    title: str,
    passport: dict[str, Any],
    *,
    strict: bool = False,
) -> bool:
    state = load_json(novel_dir / "novel_state.json", {})
    strict = strict or (isinstance(state, dict) and state.get("knowledge_gate") == "strict")
    try:
        result = build_and_save_chapter_pack(
            project_root=workspace_root(),
            novel_dir=novel_dir,
            chapter=chapter,
            title=title,
            strict=strict,
        )
    except Exception as exc:
        passport["pipeline"]["knowledge_pack"] = "fail"
        print(f"[FAIL] 生成知识包失败: {exc}", file=sys.stderr)
        return False

    passport["inputs"]["knowledge_pack"] = rel(result["pack_path"], novel_dir)
    passport["knowledge_pack_missing"] = {
        "required": result["missing_required"],
        "selected": result["missing_selected"],
    }
    passport["pipeline"]["knowledge_pack"] = result["status"]
    print(f"[OK] 已生成章节知识包: {result['pack_path']}")

    missing = [*result["missing_required"], *result["missing_selected"]]
    if missing:
        print(
            "[FAIL] 知识包存在缺失项（strict 模式阻断）："
            if result["status"] == "fail"
            else "[WARN] 知识包存在缺失项（strict 模式下会阻断）："
        )
        for item in missing:
            print(f"  - {item}")
    return result["status"] != "fail"


def validate_and_apply_truth_delta(
    novel_dir: Path,
    chapter: int,
    title: str,
    passport: dict[str, Any],
    *,
    apply_changes: bool,
) -> bool:
    chapter_file = find_chapter_file(novel_dir, chapter)
    if chapter_file:
        candidates_report = novel_dir / "素材" / f"truth_delta_candidates_ch{chapter:03d}.json"
        candidates_review = novel_dir / "素材" / f"truth_delta_candidates_ch{chapter:03d}.md"
        extract_result = run_command(
            [
                sys.executable,
                str(TRUTH_SCRIPT),
                "extract-delta",
                "--novel-dir",
                str(novel_dir),
                "--chapter",
                str(chapter),
                "--title",
                title,
                "--chapter-file",
                str(chapter_file),
                "--output",
                str(candidates_report),
                "--markdown-output",
                str(candidates_review),
                "--patch-delta",
            ],
            "提取 truth delta 候选事实",
        )
        passport["pipeline"]["truth_delta_extract"] = extract_result["status"]
        passport["inputs"]["truth_delta_candidates"] = rel(candidates_report, novel_dir)
        passport["inputs"]["truth_delta_candidates_review"] = rel(candidates_review, novel_dir)
        if extract_result["returncode"] != 0:
            return False

    delta_report = novel_dir / "素材" / f"truth_delta_ch{chapter:03d}.json"
    validate_result = run_command(
        [
            sys.executable,
            str(TRUTH_SCRIPT),
            "validate-delta",
            "--novel-dir",
            str(novel_dir),
            "--chapter",
            str(chapter),
            "--title",
            title,
            "--output",
            str(delta_report),
            "--create-template",
        ],
        "校验章节 truth delta",
    )
    passport["pipeline"]["truth_delta"] = validate_result["status"]
    passport["inputs"]["truth_delta_report"] = rel(delta_report, novel_dir)
    if validate_result["returncode"] != 0:
        return False
    if not apply_changes:
        passport["pipeline"]["truth_sync"] = "blocked"
        print("章节基础审计未全部通过，truth delta 已校验但暂不同步到真相文件。")
        return False

    apply_report = novel_dir / "素材" / f"truth_apply_ch{chapter:03d}.json"
    apply_result = run_command(
        [
            sys.executable,
            str(TRUTH_SCRIPT),
            "apply-delta",
            "--novel-dir",
            str(novel_dir),
            "--chapter",
            str(chapter),
            "--output",
            str(apply_report),
        ],
        "同步章节事实到真相文件",
    )
    passport["pipeline"]["truth_sync"] = apply_result["status"]
    passport["inputs"]["truth_apply_report"] = rel(apply_report, novel_dir)
    return apply_result["returncode"] == 0


def run_normalizer(novel_dir: Path, chapter: int, title: str, chapter_file: Path, passport: dict[str, Any]) -> bool:
    json_report = novel_dir / "素材" / f"normalizer_ch{chapter:03d}.json"
    md_report = novel_dir / "素材" / f"chapter_{chapter:03d}_normalizer_task.md"
    result = run_command(
        [
            sys.executable,
            str(TRUTH_SCRIPT),
            "normalize",
            "--novel-dir",
            str(novel_dir),
            "--chapter",
            str(chapter),
            "--title",
            title,
            "--chapter-file",
            str(chapter_file),
            "--json-output",
            str(json_report),
            "--output",
            str(md_report),
        ],
        "字数归一化检查",
    )
    passport["pipeline"]["normalizer"] = result["status"]
    passport["inputs"]["normalizer_report"] = rel(json_report, novel_dir)
    if result["returncode"] != 0:
        passport["inputs"]["normalizer_task"] = rel(md_report, novel_dir)
    return result["returncode"] == 0


def run_command(cmd: list[str], description: str) -> dict[str, Any]:
    started_at = now_iso()
    started_clock = time.perf_counter()
    print(f"\n{'=' * 64}")
    print(description)
    print(" ".join(cmd))
    print("=" * 64)
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=workspace_root(),
        env=env,
    )
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    status = "pass" if result.returncode == 0 else "fail"
    print(f"{description}: {status} (exit {result.returncode})")
    payload = {
        "status": status,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "command": cmd,
    }
    try:
        ledger_record = record_subprocess(
            cmd,
            description,
            payload,
            started_at=started_at,
            finished_at=now_iso(),
            duration_ms=round((time.perf_counter() - started_clock) * 1000),
        )
        if ledger_record:
            payload["run_id"] = ledger_record["run_id"]
    except OSError as exc:
        print(f"[WARN] 写入流水线运行账本失败: {exc}", file=sys.stderr)
    return payload


def pre_check_score(report_path: Path) -> int | None:
    report = load_json(report_path, {})
    score = report.get("score")
    return score if isinstance(score, int) else None


def find_style_dna(novel_dir: Path) -> Path | None:
    candidates = [
        find_memory_dir(novel_dir) / "style_dna_baseline.json",
        find_memory_dir(novel_dir) / "style_dna.json",
        novel_dir / "style_dna.json",
    ]
    return next((p for p in candidates if p.exists()), None)


def find_characters_file(novel_dir: Path) -> Path | None:
    memory_dir = find_memory_dir(novel_dir)
    for pattern in ["characters.json", "character_*.json", "人物*.json"]:
        matches = sorted(memory_dir.glob(pattern)) if memory_dir.exists() else []
        if matches:
            return matches[0]
    return None


# ============================================================
# P3: 章节骨架生成
# ============================================================

def generate_chapter_skeleton(
    novel_dir: Path,
    chapter: int,
    title: str,
) -> Path | None:
    """写正文前生成章节骨架，包含锚点/冲突/记忆更新清单。

    从细纲、上一章摘要、人物档案中提取信息，生成结构化骨架供写作参考。
    """
    skeleton_path = novel_dir / "素材" / f"skeleton_ch{chapter:03d}.md"
    lines = [f"# 第{chapter}章 骨架 — {title}", ""]

    # 1. 读取细纲
    outline_dir = novel_dir / "细纲"
    outline_content = ""
    if outline_dir.exists():
        for f in sorted(outline_dir.glob("*.md")):
            text = f.read_text(encoding="utf-8")
            # 尝试找到本章对应的细纲段落
            patterns = [
                rf"第{chapter}章",
                rf"第{chapter}节",
                rf"chapter[ _]?{chapter}",
            ]
            for pat in patterns:
                match = re.search(pat, text, re.IGNORECASE)
                if match:
                    # 提取到下一个章节标题之间的内容
                    next_ch = re.search(r"第\d+[章节]", text[match.end():])
                    end = match.end() + next_ch.start() if next_ch else len(text)
                    outline_content = text[match.start():end].strip()
                    break
            if outline_content:
                break

    if outline_content:
        lines.append("## 细纲要点")
        lines.append(outline_content[:1000])
        lines.append("")
    else:
        lines.append("## 细纲要点")
        lines.append("> ⚠️ 未找到本章细纲，请参考总大纲。")
        lines.append("")

    # 2. 上一章摘要
    prev_summary_path = novel_dir / "摘要" / f"chapter_{chapter - 1:03d}_summary.json"
    if prev_summary_path.exists():
        prev = load_json(prev_summary_path, {})
        if isinstance(prev, dict):
            lines.append("## 上一章回顾")
            summary = prev.get("summary", prev.get("plot_summary", ""))
            if summary:
                lines.append(f"- **摘要**: {summary}")
            key_events = prev.get("key_events", [])
            if key_events:
                lines.append(f"- **关键事件**: {', '.join(str(e) for e in key_events)}")
            cliffhanger = prev.get("cliffhanger", prev.get("hook", ""))
            if cliffhanger:
                lines.append(f"- **悬念/钩子**: {cliffhanger}")
            lines.append("")

    # 3. 活跃角色状态
    memory_dir = find_memory_dir(novel_dir)
    characters_file = find_characters_file(novel_dir)
    if characters_file:
        chars_data = load_json(characters_file, {})
        if isinstance(chars_data, dict):
            memories = chars_data.get("memories", [])
            active_chars: list[str] = []
            for mem in memories:
                data = mem.get("data", {}) if isinstance(mem, dict) else {}
                if isinstance(data, dict) and data.get("basic_info"):
                    name = data["basic_info"].get("name", "")
                    if name:
                        active_chars.append(name)
            if active_chars:
                lines.append("## 活跃角色")
                for name in active_chars[:10]:
                    lines.append(f"- {name}")
                lines.append("")

    # 4. 写作约束清单
    lines.append("## 写作约束清单")
    lines.append("")
    lines.append("### 开篇锚点（选择一种）")
    lines.append("- [ ] 动作开场：角色正在做某事")
    lines.append("- [ ] 对话开场：角色正在说某话")
    lines.append("- [ ] 环境开场：场景描写引入")
    lines.append("- [ ] 心理开场：角色内心活动")
    lines.append("- [ ] 悬念开场：抛出问题/异常")
    lines.append("")

    lines.append("### 核心冲突")
    lines.append("- [ ] 本章核心冲突已明确：______")
    lines.append("- [ ] 冲突在前300字已出现")
    lines.append("- [ ] 冲突有推进（不是原地打转）")
    lines.append("")

    lines.append("### 结尾目标（选择一种）")
    lines.append("- [ ] 悬念钩子：留下未解问题")
    lines.append("- [ ] 打脸前奏：即将反击/逆转")
    lines.append("- [ ] 新冲突引入：更大的问题出现")
    lines.append("- [ ] 情感高潮：角色情感爆发")
    lines.append("- [ ] 信息炸弹：揭示关键信息")
    lines.append("")

    lines.append("### 记忆更新清单")
    lines.append("- [ ] 角色状态变化已记录")
    lines.append("- [ ] 新出现的地点/势力已记录")
    lines.append("- [ ] 伏笔设置/回收已标注")
    lines.append("- [ ] 物理状态（钱/物品/位置）已更新")
    lines.append("")

    lines.append("### 写中自检（每300-500字）")
    lines.append("- [ ] 有没有无聊的段落？")
    lines.append("- [ ] 有没有重复的内容？")
    lines.append("- [ ] 有没有推进剧情？")
    lines.append("- [ ] 对话比例是否健康（≥25%）？")
    lines.append("- [ ] 人物行为是否符合设定？")
    lines.append("")

    skeleton_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[OK] 章节骨架已生成: {skeleton_path}")
    return skeleton_path


def stage_pre(args: argparse.Namespace) -> bool:
    novel_dir = resolve_path(args.novel_dir)
    if not ensure_bootstrap_gate(novel_dir):
        return False
    if not ensure_prev_chapter_audited(
        novel_dir,
        args.chapter,
        allow_override=args.override_prev_audit,
        stage="pre",
        override_reason=getattr(args, "override_reason", ""),
    ):
        return False
    ensure_dirs(novel_dir)
    if not ensure_truth_files(novel_dir):
        return False
    memory_dir = resolve_path(args.memory_dir) if args.memory_dir else find_memory_dir(novel_dir)
    chapter = args.chapter
    title = args.title or f"第{chapter}章"

    chapter_file = find_chapter_file(novel_dir, chapter)
    passport = load_passport(novel_dir, chapter, title, chapter_file)
    save_workflow_checkpoint(
        novel_dir,
        chapter,
        passport,
        stage="pre",
        status="running",
        next_action="pre",
    )
    knowledge_ok = build_and_save_knowledge_pack(
        novel_dir,
        chapter,
        title,
        passport,
        strict=getattr(args, "strict_knowledge", False),
    )
    truth_ok = compile_truth_inputs(novel_dir, chapter, title, passport)
    delta_template_ok = create_truth_delta_template(novel_dir, chapter, title, passport)

    pack_path = novel_dir / "摘要" / f"chapter_{chapter:03d}_pack.json"
    cmd = [
        sys.executable,
        str(MEMORY_SCRIPT),
        "chapter-pack",
        "--chapter",
        str(chapter),
        "--memory-dir",
        str(memory_dir),
        "--output",
        str(pack_path),
    ]
    pack_result = run_command(cmd, "生成章节记忆包")
    passport["pipeline"]["memory_pack"] = pack_result["status"]
    if pack_path.exists():
        passport["inputs"]["memory_pack"] = rel(pack_path, novel_dir)

    pre_report = novel_dir / "素材" / f"pre_check_ch{chapter:03d}.json"
    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "pre_write_check.py"),
        "--novel-dir",
        str(novel_dir),
        "--chapter",
        str(chapter),
        "--title",
        title,
        "--memory-dir",
        str(memory_dir),
        "--output",
        str(pre_report),
    ]
    if args.answers_file:
        cmd.extend(["--answers-file", str(resolve_path(args.answers_file))])
    pre_result = run_command(cmd, "9问必答检查")
    score = pre_check_score(pre_report)
    passport["pipeline"]["pre_write_check"] = pre_result["status"]
    passport["inputs"]["pre_check_report"] = rel(pre_report, novel_dir)
    passport["pre_write_score"] = score

    if chapter_file and chapter_file.exists():
        text = chapter_file.read_text(encoding="utf-8")
        passport["word_count"] = count_chinese_chars(text)
        passport["chapter_file"] = rel(chapter_file, novel_dir)

    # 生成章节骨架
    generate_chapter_skeleton(novel_dir, chapter, title)
    pre_ok = (
        knowledge_ok
        and
        truth_ok
        and delta_template_ok
        and pre_result["returncode"] == 0
        and (pack_result["returncode"] == 0 or args.allow_missing_memory)
    )
    if pre_ok:
        # 先记录 pre 已完成，再进入等待正文的 draft 状态，避免
        # resume_point 看起来像 pre 一直处于 pending。
        save_workflow_checkpoint(
            novel_dir,
            chapter,
            passport,
            stage="pre",
            status="pass",
            next_action="write_then_post",
        )
        save_workflow_checkpoint(
            novel_dir,
            chapter,
            passport,
            stage="draft",
            status="pending",
            next_action="write_then_post",
        )
    else:
        save_workflow_checkpoint(
            novel_dir,
            chapter,
            passport,
            stage="pre",
            status="blocked",
            next_action="pre",
            error="写前检查未通过",
        )
    if pre_ok and args.scene_plan:
        try:
            scene_plan_payload = load_json(resolve_path(args.scene_plan), [])
            scene_plan = scene_plan_payload.get("scenes") if isinstance(scene_plan_payload, dict) else scene_plan_payload
            if not isinstance(scene_plan, list):
                raise ValueError("场景计划必须是数组或 {scenes: [...]} 对象")
            initialize_scene_plan(novel_dir, chapter, scene_plan)
            print(f"[OK] 场景 passport 已初始化: 第{chapter}章")
        except (OSError, ValueError, TypeError) as exc:
            print(f"[FAIL] 场景计划初始化失败: {exc}", file=sys.stderr)
            return False
    return pre_ok


def prepare_post_context(args: argparse.Namespace, phase: str) -> tuple[Path, int, str, Path, Path, dict[str, Any]] | None:
    novel_dir = resolve_path(args.novel_dir)
    if not ensure_bootstrap_gate(novel_dir):
        return None
    if not ensure_prev_chapter_audited(
        novel_dir,
        args.chapter,
        allow_override=args.override_prev_audit,
        stage=f"post:{phase}",
        override_reason=getattr(args, "override_reason", ""),
    ):
        return None
    ensure_dirs(novel_dir)
    if not ensure_truth_files(novel_dir):
        return None
    chapter = args.chapter
    title = args.title or f"第{chapter}章"
    chapter_file = find_chapter_file(novel_dir, chapter)
    if not chapter_file:
        print(f"未找到第{chapter}章正文文件", file=sys.stderr)
        return None
    passport_file = passport_path(novel_dir, chapter)
    passport = load_passport(novel_dir, chapter, title, chapter_file)
    passport["chapter_file"] = rel(chapter_file, novel_dir)
    passport["word_count"] = count_chinese_chars(chapter_file.read_text(encoding="utf-8"))
    return novel_dir, chapter, title, chapter_file, passport_file, passport


def post_audit_phase(args: argparse.Namespace) -> bool:
    context = prepare_post_context(args, "audit")
    if context is None:
        return False
    novel_dir, chapter, title, chapter_file, _passport_file, passport = context
    save_workflow_checkpoint(novel_dir, chapter, passport, stage="audit", status="running", next_action="post --phase audit")

    platform_report = novel_dir / "素材" / f"platform_preflight_ch{chapter:03d}.json"
    gate_result = run_command(
        [
            sys.executable,
            str(SCRIPTS_DIR / "writing_gate.py"),
            "--chapter", str(chapter_file),
            "--novel-dir", str(novel_dir),
            "--report", str(platform_report),
        ],
        "Writing Gate 检查",
    )
    passport["pipeline"]["writing_gate"] = gate_result["status"]
    passport["pipeline"]["platform_preflight"] = gate_result["status"]
    passport["inputs"]["platform_preflight"] = rel(platform_report, novel_dir)

    audit_report = novel_dir / "素材" / f"audit_ch{chapter:03d}.json"
    audit_cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "post_write_audit.py"),
        "--chapter-file", str(chapter_file), "--title", title, "--output", str(audit_report),
    ]
    prev_file = find_chapter_file(novel_dir, chapter - 1) if chapter > 1 else None
    if prev_file:
        audit_cmd.extend(["--prev-file", str(prev_file)])
    novel_state = novel_dir / "novel_state.json"
    if novel_state.exists():
        audit_cmd.extend(["--novel-state", str(novel_state)])
    audit_result = run_command(audit_cmd, "写后审计")
    passport["pipeline"]["post_write_audit"] = audit_result["status"]
    passport["inputs"]["audit_report"] = rel(audit_report, novel_dir)

    normalizer_ok = run_normalizer(novel_dir, chapter, title, chapter_file, passport)

    opening_ok = True
    if chapter <= 3:
        opening_report = novel_dir / "素材" / f"opening_score_ch{chapter:03d}.json"
        opening_result = run_command(
            [sys.executable, str(PROJECT_ROOT / "tools" / "opening_score.py"), str(chapter_file), "--json"],
            "开篇评分",
        )
        if opening_result["returncode"] == 0:
            try:
                opening_payload = json.loads(opening_result["stdout"])
                score = int(opening_payload.get("total", 0))
            except (ValueError, TypeError, json.JSONDecodeError):
                opening_payload = {}
                score = 0
            save_json(opening_report, opening_payload)
            passport["pipeline"]["opening_score"] = "pass" if score >= 70 else "warning"
            passport["inputs"]["opening_score_report"] = rel(opening_report, novel_dir)
            if score < 70:
                print(
                    f"[WARN] 开篇评分 {score}/100 低于 70，建议按开篇 100 分卡重构前 300 字/第一章。",
                    file=sys.stderr,
                )
        else:
            passport["pipeline"]["opening_score"] = "skipped"

    ok = gate_result["returncode"] == 0 and audit_result["returncode"] == 0 and normalizer_ok and opening_ok
    save_workflow_checkpoint(
        novel_dir, chapter, passport,
        stage="audit", status="pass" if ok else "blocked",
        next_action="post --phase truth" if ok else "post --phase audit",
        error="" if ok else "写作 Gate、审计或字数检查未通过",
    )
    return ok


def post_truth_phase(args: argparse.Namespace) -> bool:
    context = prepare_post_context(args, "truth")
    if context is None:
        return False
    novel_dir, chapter, title, _chapter_file, _passport_file, passport = context
    if passport["pipeline"].get("post_write_audit") != "pass" or passport["pipeline"].get("normalizer") != "pass":
        print("[BLOCKED] truth 阶段要求先通过 audit 阶段。", file=sys.stderr)
        save_workflow_checkpoint(novel_dir, chapter, passport, stage="truth", status="blocked", next_action="post --phase audit", error="audit 尚未通过")
        return False
    save_workflow_checkpoint(novel_dir, chapter, passport, stage="truth", status="running", next_action="post --phase truth")
    ok = validate_and_apply_truth_delta(novel_dir, chapter, title, passport, apply_changes=True)
    save_workflow_checkpoint(
        novel_dir, chapter, passport,
        stage="truth", status="pass" if ok else "blocked",
        next_action="post --phase quality" if ok else "post --phase truth",
        error="" if ok else "truth delta 未确认或同步失败",
    )
    return ok


def post_quality_phase(args: argparse.Namespace) -> bool:
    context = prepare_post_context(args, "quality")
    if context is None:
        return False
    novel_dir, chapter, _title, chapter_file, _passport_file, passport = context
    missing_truth = [
        key for key in ("truth_delta", "truth_sync")
        if passport["pipeline"].get(key) != "pass"
    ]
    if missing_truth:
        print(f"[BLOCKED] quality 阶段要求 truth 先通过: {', '.join(missing_truth)}", file=sys.stderr)
        save_workflow_checkpoint(
            novel_dir,
            chapter,
            passport,
            stage="quality",
            status="blocked",
            next_action="post --phase truth",
            error="truth 阶段尚未完成",
        )
        return False
    mode, profile = quality_profile(novel_dir, getattr(args, "quality_mode", ""))
    passport["quality_mode"] = mode
    save_workflow_checkpoint(novel_dir, chapter, passport, stage="quality", status="running", next_action="post --phase quality")
    style_dna = find_style_dna(novel_dir)
    if style_dna:
        style_report = novel_dir / "素材" / f"style_ch{chapter:03d}.json"
        style_result = run_command(
            [sys.executable, str(MEMORY_SCRIPTS_DIR / "style_calibrator.py"), "--input", str(chapter_file), "--style-dna", str(style_dna), "--output", str(style_report)],
            "风格校准",
        )
        passport["pipeline"]["style_calibration"] = style_result["status"]
        passport["inputs"]["style_report"] = rel(style_report, novel_dir)
        style_ok = style_result["returncode"] == 0
    else:
        passport["pipeline"]["style_calibration"] = "skipped"
        style_ok = True
        print("未找到 style DNA，跳过风格校准")

    characters_file = find_characters_file(novel_dir)
    if characters_file:
        character_report = novel_dir / "素材" / f"character_ch{chapter:03d}.json"
        character_result = run_command(
            [sys.executable, str(MEMORY_SCRIPTS_DIR / "character_consistency_checker.py"), "--input", str(chapter_file), "--characters", str(characters_file), "--output", str(character_report)],
            "人物一致性检查",
        )
        passport["pipeline"]["character_consistency"] = character_result["status"]
        passport["inputs"]["character_report"] = rel(character_report, novel_dir)
        character_ok = character_result["returncode"] == 0
    else:
        passport["pipeline"]["character_consistency"] = "skipped"
        character_ok = True
        print("未找到人物档案，跳过人物一致性检查")

    review_path = quality_review_path(novel_dir, chapter)
    supplied_review = getattr(args, "quality_review_report", "")
    if supplied_review:
        supplied_path = resolve_path(supplied_review)
        if not supplied_path.is_file():
            print(f"[FAIL] quality review 报告不存在: {supplied_path}", file=sys.stderr)
            review_ok = False
        else:
            review_path.parent.mkdir(parents=True, exist_ok=True)
            review_path.write_bytes(supplied_path.read_bytes())
            review_payload = load_json(review_path, {})
            review_ok = isinstance(review_payload, dict) and str(review_payload.get("status", "")).lower() in {"pass", "passed", "ok"}
    elif profile["requires_quality_review"]:
        review_payload = load_json(review_path, {})
        review_ok = isinstance(review_payload, dict) and str(review_payload.get("status", "")).lower() in {"pass", "passed", "ok"}
        if not review_ok:
            print(f"[BLOCKED] {mode} 模式需要人工确认的 quality review: {review_path}", file=sys.stderr)
    else:
        review_ok = True
    passport["pipeline"]["quality_review"] = "pass" if review_ok and review_path.exists() else "skipped" if not profile["requires_quality_review"] else "pending"
    if review_path.exists():
        passport["inputs"]["quality_review"] = rel(review_path, novel_dir)

    # 结构化审稿门禁：文件存在就必须被遵守；tribunal 模式要求必须有。
    structured_review = review_gate(novel_dir, chapter)
    if structured_review["status"] == "missing":
        passport["pipeline"]["review_result"] = "missing"
        if mode == "tribunal":
            review_result_ok = False
            print(
                f"[BLOCKED] {mode} 模式要求结构化审稿结果: {chapter_review_path(novel_dir, chapter)}",
                file=sys.stderr,
            )
        else:
            review_result_ok = True
    else:
        review_result_ok = structured_review["status"] == "pass"
        passport["pipeline"]["review_result"] = "pass" if review_result_ok else "fail"
        passport["inputs"]["review_result"] = rel(structured_review["path"], novel_dir)
        if structured_review["status"] == "invalid":
            print("[BLOCKED] 审稿结果契约无效:", file=sys.stderr)
            for error in structured_review["report"]["errors"]:
                print(f"  - {error}", file=sys.stderr)
        elif structured_review["status"] == "blocked":
            print(
                f"[BLOCKED] 审稿存在 {structured_review['blocking_count']} 个 blocking issue:",
                file=sys.stderr,
            )
            for issue in structured_review["issues"]:
                if issue["severity"] != "blocker":
                    continue
                print(f"  - {issue['id']} [{issue['dimension']}] {issue['evidence']}", file=sys.stderr)
                if issue["repair"]:
                    print(f"    修复: {issue['repair']}", file=sys.stderr)
        elif structured_review["status"] == "stale":
            print("[BLOCKED] 审稿结果已过期：正文 SHA-256 与审稿记录不一致。", file=sys.stderr)
            for error in structured_review["report"]["errors"]:
                print(f"  - {error}", file=sys.stderr)
            print("  请重新调用 reviewer，不要复用旧审稿。", file=sys.stderr)

    tension_report = validate_chapter_tension(novel_dir, chapter)
    passport["pipeline"]["tension_curve"] = tension_report["status"]
    passport["inputs"]["tension_report"] = rel(Path(tension_report["report_path"]), novel_dir)
    tension_ok = tension_report["status"] in {"pass", "skipped"}
    if not tension_ok:
        print(f"[BLOCKED] 张力曲线契约未通过: {', '.join(tension_report['errors'])}", file=sys.stderr)

    contract_report = validate_chapter_contracts(novel_dir, chapter, passport=passport)
    contract_path = save_contract_report(novel_dir, chapter, contract_report)
    passport["pipeline"]["contract_validation"] = contract_report["status"]
    passport["inputs"]["contract_report"] = rel(contract_path, novel_dir)
    contract_ok = contract_report["status"] == "pass"
    if not contract_ok:
        print(f"[BLOCKED] JSON 契约未通过: {', '.join(contract_report['errors'])}", file=sys.stderr)

    ok = style_ok and character_ok and review_ok and review_result_ok and tension_ok and contract_ok
    save_workflow_checkpoint(
        novel_dir, chapter, passport,
        stage="quality", status="pass" if ok else "blocked",
        next_action="post --phase memory" if ok else "post --phase quality",
        error="风格、人物一致性或结构化审稿检查失败" if not ok else "",
    )
    return ok


def post_memory_phase(args: argparse.Namespace) -> bool:
    context = prepare_post_context(args, "memory")
    if context is None:
        return False
    novel_dir, chapter, _title, _chapter_file, _passport_file, passport = context
    save_workflow_checkpoint(novel_dir, chapter, passport, stage="memory", status="running", next_action="post --phase memory")
    summary_file = novel_dir / "摘要" / f"chapter_{chapter:03d}_summary.json"
    if summary_file.exists():
        memory_dir = resolve_path(args.memory_dir) if args.memory_dir else find_memory_dir(novel_dir)
        sync_result = run_command(
            [sys.executable, str(MEMORY_SCRIPT), "sync-chapter", "--input", str(summary_file), "--memory-dir", str(memory_dir)],
            "章节摘要回填",
        )
        passport["pipeline"]["memory_sync"] = sync_result["status"]
        ok = sync_result["returncode"] == 0
    else:
        passport["pipeline"]["memory_sync"] = "pending"
        print(f"未找到章节摘要，记忆回填保持 pending: {summary_file}")
        ok = True

    ledger_result = run_command(
        [
            sys.executable,
            str(PROJECT_ROOT / "tools" / "emotion_ledger.py"),
            "sync",
            "--novel-dir",
            str(novel_dir),
        ],
        "情绪账同步",
    )
    passport["pipeline"]["emotion_ledger"] = ledger_result["status"]
    if (novel_dir / "追踪" / "情绪账.md").is_file():
        passport["inputs"]["emotion_ledger"] = "追踪/情绪账.md"
    ok = ok and ledger_result["returncode"] == 0

    save_workflow_checkpoint(
        novel_dir, chapter, passport,
        stage="memory", status="pass" if ok else "blocked",
        next_action="post --phase commit" if ok else "post --phase memory",
        error="记忆回填失败" if not ok else "",
    )
    return ok


def refresh_dashboards_safe(novel_dir: Path) -> None:
    """Refresh dashboards only when the book is inside the active workspace."""
    workspace = workspace_root().resolve()
    try:
        Path(novel_dir).resolve().relative_to(workspace)
    except ValueError:
        return
    try:
        write_dashboards(workspace, novel_dir)
    except (OSError, ValueError):
        pass


def post_commit_phase(args: argparse.Namespace) -> bool:
    context = prepare_post_context(args, "commit")
    if context is None:
        return False
    novel_dir, chapter, title, chapter_file, passport_file, passport = context
    requested_mode = passport.get("quality_mode", "")
    mode, _profile = quality_profile(
        novel_dir,
        requested_mode if requested_mode in {"balanced", "tribunal"} else "",
    )
    passport["quality_mode"] = mode
    save_workflow_checkpoint(novel_dir, chapter, passport, stage="commit", status="running", next_action="post --phase commit")
    required_ok = all(
        passport["pipeline"].get(key) == "pass"
        for key in ("writing_gate", "post_write_audit", "normalizer", "truth_delta", "truth_sync")
    )
    if passport.get("quality_mode") == "tribunal" and passport["pipeline"].get("quality_review") != "pass":
        required_ok = False
    structured_review = review_gate(novel_dir, chapter)
    passport["pipeline"]["review_result"] = {
        "missing": "missing",
        "pass": "pass",
        "blocked": "fail",
        "invalid": "fail",
        "stale": "fail",
    }.get(structured_review["status"], "missing")
    if structured_review["status"] in {"blocked", "invalid", "stale"} or (
        mode == "tribunal" and structured_review["status"] == "missing"
    ):
        required_ok = False
        print(
            f"[BLOCKED] 结构化审稿未通过（{structured_review['status']}），禁止 commit。",
            file=sys.stderr,
        )
    if load_tension_contract(novel_dir).get("enabled") and passport["pipeline"].get("tension_curve") != "pass":
        required_ok = False
    contract_report = validate_chapter_contracts(novel_dir, chapter, passport=passport)
    contract_path = save_contract_report(novel_dir, chapter, contract_report)
    passport["pipeline"]["contract_validation"] = contract_report["status"]
    passport["inputs"]["contract_report"] = rel(contract_path, novel_dir)
    if contract_report["status"] != "pass":
        required_ok = False
    scene_index = passport.get("scene_index", {})
    if isinstance(scene_index, dict) and scene_index.get("enabled") and scene_index.get("status") != "pass":
        required_ok = False
        print("[BLOCKED] 已启用场景 passport，但并非所有场景都通过。", file=sys.stderr)
    commit_file = chapter_commit_path(novel_dir, chapter)
    review_artifact = chapter_review_path(novel_dir, chapter)
    commit_payload: dict[str, Any] | None = None

    def input_file(key: str) -> Path | None:
        value = passport.get("inputs", {}).get(key, "")
        if not value:
            return None
        candidate = Path(value)
        return candidate if candidate.is_absolute() else novel_dir / candidate

    def input_file_or(key: str, fallback: Path) -> Path:
        return input_file(key) or fallback

    # Build the final passport BEFORE writing the commit. The commit binds
    # artifact hashes, so saving the passport after the commit would make the
    # commit invalid immediately.
    revision = ensure_current_revision(novel_dir, chapter, source="writing")
    passport["revision"] = {
        "revision_id": revision["revision_id"],
        "version": revision["version"],
        "content_hash": revision["content_hash"],
        "source": revision["source"],
    }
    expected_commit_id = commit_id_for(chapter, chapter_file)

    if required_ok:
        passport["commit"] = {
            "status": "accepted",
            "path": rel(commit_file, novel_dir),
            "id": expected_commit_id,
            "created_at": now_iso(),
        }
        passport["pipeline_result"] = "pass"
        passport["workflow"] = transition(
            passport.get("workflow", {}),
            "commit",
            "pass",
            next_action="pre",
        )
        save_passport(novel_dir, chapter, passport)
        audit_file = find_audit_report(novel_dir, chapter) or novel_dir / "素材" / f"audit_ch{chapter:03d}.json"
        try:
            commit_payload = record_chapter_commit(
                novel_dir,
                chapter,
                chapter_file=chapter_file,
                artifacts={
                    "chapter": chapter_file,
                    "passport": passport_file,
                    "audit": audit_file,
                    "truth_delta": input_file_or("truth_delta", novel_dir / "摘要" / f"chapter_{chapter:03d}_truth_delta.json"),
                    "truth_delta_report": input_file_or("truth_delta_report", novel_dir / "素材" / f"truth_delta_ch{chapter:03d}.json"),
                    "truth_apply_report": input_file_or("truth_apply_report", novel_dir / "素材" / f"truth_apply_ch{chapter:03d}.json"),
                    "normalizer_report": input_file("normalizer_report"),
                    "style_report": input_file("style_report"),
                    "character_report": input_file("character_report"),
                    "review_result": review_artifact if review_artifact.is_file() else None,
                },
                pipeline=passport.get("pipeline", {}),
            )
            print(f"[OK] 第{chapter}章提交记录已生成: {commit_file}")
        except (FileNotFoundError, OSError, ValueError) as exc:
            commit_payload = None
            print(f"[FAIL] 章节提交记录生成失败: {exc}", file=sys.stderr)

    if commit_payload is None:
        passport["commit"] = {
            "status": "blocked",
            "path": rel(commit_file, novel_dir),
            "id": "",
            "created_at": "",
        }
        passport["pipeline_result"] = "fail"
        passport["workflow"] = transition(
            passport.get("workflow", {}),
            "commit",
            "blocked",
            next_action="post --phase audit",
            error="必需阶段未通过或提交记录生成失败",
        )
        save_passport(novel_dir, chapter, passport)
    update_novel_state(
        novel_dir,
        chapter=chapter,
        word_count=passport.get("word_count"),
        audit_report=passport["inputs"].get("audit_report"),
        audit_status=passport["pipeline"].get("post_write_audit"),
        passport=rel(passport_file, novel_dir),
        pipeline_result=passport.get("pipeline_result"),
        commit_update={
            "status": "accepted" if commit_payload else "blocked",
            "path": rel(commit_file, novel_dir),
            "id": commit_payload.get("commit_id", "") if commit_payload else "",
        },
        workflow_update=passport["workflow"],
    )
    refresh_dashboards_safe(novel_dir)
    if not commit_payload:
        print("\n[INFO] 审计未通过，自动生成修复计划...")
        generate_fix_plan(novel_dir, chapter, title)
    else:
        governance_check(novel_dir, chapter)
        if not getattr(args, "no_backup", False):
            try:
                from novel_creation_promax.core.chapter_backup import snapshot_chapter

                snapshot = snapshot_chapter(
                    novel_dir,
                    chapter,
                    reason="post commit",
                    keep=5,
                    chapter_file=chapter_file,
                )
                print(f"[OK] 已备份第{chapter}章快照: {snapshot['path']}")
            except (OSError, ValueError) as exc:
                print(f"[WARN] 章节快照备份失败: {exc}", file=sys.stderr)
    return bool(commit_payload)


def run_post_phase(args: argparse.Namespace, phase: str) -> bool:
    handlers = {
        "audit": post_audit_phase,
        "truth": post_truth_phase,
        "quality": post_quality_phase,
        "memory": post_memory_phase,
        "commit": post_commit_phase,
    }
    with chapter_lock(resolve_path(args.novel_dir), args.chapter):
        return handlers[phase](args)


def stage_post(args: argparse.Namespace) -> bool:
    phases = POST_PHASES if args.phase == "all" else (args.phase,)
    for phase in phases:
        try:
            if not run_post_phase(args, phase):
                return False
        except RuntimeError as exc:
            print(f"[BLOCKED] {exc}", file=sys.stderr)
            return False
    return True


def generate_fix_plan(novel_dir: Path, chapter: int, title: str) -> dict[str, Any] | None:
    """分析审计报告，生成结构化修复计划。

    返回 fix_plan dict，同时保存为 JSON + Markdown。
    如果审计已通过，返回 None。
    """
    audit_report_path = find_audit_report(novel_dir, chapter)
    if audit_report_path is None:
        print(
            f"[WARN] 未找到审计报告: {novel_dir / '素材' / f'audit_ch{chapter:03d}.json'}",
            file=sys.stderr,
        )
        return None

    # 统一读取层：兼容 legacy 扁平格式与当前 wrapped 格式
    audit = load_audit(novel_dir, chapter)
    if not audit:
        return None

    # 检查是否已通过
    if audit.get("status") == "pass":
        print("[OK] 审计已通过，无需生成修复计划。")
        return None

    fix_actions: list[dict[str, Any]] = []

    # 1. AI 词问题（canonical 为 [{"word","count"}]）
    ai_items = audit.get("ai_words") or []
    if ai_items:
        found = [f"{item['word']}×{item['count']}" for item in ai_items]
        fix_actions.append({
            "category": "ai_words",
            "priority": "high",
            "description": f"清除 {len(found)} 种 AI 词/禁用词（共 {audit.get('ai_word_count', 0)} 次）",
            "details": found[:20],  # 最多列出20个
            "instruction": "逐个替换：用具体动作/感官描写替代抽象词汇。参照'每段三刀'法则，每段至少3处具体化修改。",
        })

    # 2. 对话比例问题（canonical 为 float | None）
    ratio = audit.get("dialogue_ratio")
    threshold = 0.25
    if isinstance(ratio, (int, float)) and ratio < threshold:
        fix_actions.append({
            "category": "dialogue_ratio",
            "priority": "medium",
            "description": f"对话比例 {ratio:.1%} 低于阈值 {threshold:.0%}",
            "instruction": "将部分叙述转为对话：用角色交流替代信息传递段落，增加对话轮次。",
        })

    # 3. 风格漂移（canonical 保留了原始扩展字段）
    style_drift = audit.get("style_drift") or audit.get("style_calibration") or {}
    if isinstance(style_drift, dict):
        drift_score = style_drift.get("drift_score", style_drift.get("score", 0))
        if isinstance(drift_score, (int, float)) and drift_score > 0.3:
            fix_actions.append({
                "category": "style_drift",
                "priority": "medium",
                "description": f"风格漂移分数 {drift_score:.2f} 偏高",
                "instruction": "回归基准风格：检查句式是否偏离 DNA，高频词是否被替换为同义词，语气是否一致。",
            })

    # 4. 人物一致性
    character = audit.get("character_consistency") or audit.get("ooc_check") or {}
    if isinstance(character, dict):
        issues = character.get("issues", character.get("ooc_detected", []))
        if isinstance(issues, list) and issues:
            fix_actions.append({
                "category": "ooc",
                "priority": "high",
                "description": f"检测到 {len(issues)} 处人物不一致",
                "details": issues[:10],
                "instruction": "对照人物档案修正：检查行为动机、说话风格、能力边界是否符合设定。",
            })

    # 5. 字数问题（canonical 为 int | None）
    count = audit.get("word_count")
    min_count = 2000
    if isinstance(count, int) and count < min_count:
        deficit = min_count - count
        fix_actions.append({
            "category": "word_count",
            "priority": "low",
            "description": f"字数 {count} 不足，差 {deficit} 字",
            "instruction": f"补充 {deficit} 字：在场景描写/心理活动/对话轮次中自然扩充，不要注水。",
        })

    # 6. 乒乓球句
    pingpong = audit.get("pingpong_sentences", audit.get("dialogue_pingpong", []))
    if isinstance(pingpong, list) and pingpong:
        fix_actions.append({
            "category": "pingpong",
            "priority": "medium",
            "description": f"检测到 {len(pingpong)} 处乒乓球短句",
            "instruction": "在对话之间插入动作锚点、环境描写、心理活动，打破连续对话的单调感。",
        })

    # 7. Gate 问题
    gate = audit.get("writing_gate", {})
    if isinstance(gate, dict) and gate.get("status") == "fail":
        gate_issues = gate.get("issues", [])
        if gate_issues:
            fix_actions.append({
                "category": "gate",
                "priority": "high",
                "description": f"Writing Gate 未通过: {len(gate_issues)} 项问题",
                "details": gate_issues[:10],
                "instruction": "逐项修复 Gate 检测到的问题。",
            })

    if not fix_actions:
        print("[WARN] 审计未通过但未识别到具体问题，建议人工检查审计报告。")
        return None

    # 按优先级排序
    priority_order = {"high": 0, "medium": 1, "low": 2}
    fix_actions.sort(key=lambda x: priority_order.get(x.get("priority", "low"), 9))

    fix_plan: dict[str, Any] = {
        "chapter": chapter,
        "title": title,
        "audit_report": rel(audit_report_path, novel_dir),
        "generated_at": now_iso(),
        "total_issues": len(fix_actions),
        "high_priority": sum(1 for a in fix_actions if a.get("priority") == "high"),
        "actions": fix_actions,
    }

    # 保存 JSON
    fix_json_path = novel_dir / "素材" / f"fix_plan_ch{chapter:03d}.json"
    save_json(fix_json_path, fix_plan)
    print(f"[OK] 修复计划已生成: {fix_json_path}")

    # 保存可读 Markdown
    fix_md_path = novel_dir / "素材" / f"fix_plan_ch{chapter:03d}.md"
    md_lines = [
        f"# 第{chapter}章 修复计划",
        f"\n> 生成时间: {fix_plan['generated_at']}",
        f"> 共 {fix_plan['total_issues']} 项问题（高优 {fix_plan['high_priority']} 项）\n",
    ]
    for i, action in enumerate(fix_actions, 1):
        icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(action.get("priority", ""), "⚪")
        md_lines.append(f"## {icon} {i}. {action['description']}")
        md_lines.append(f"\n**修复指令**: {action['instruction']}")
        if action.get("details"):
            md_lines.append("\n**涉及项**:")
            for detail in action["details"][:10]:
                md_lines.append(f"  - {detail}")
        md_lines.append("")

    fix_md_path.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"[OK] 可读修复计划: {fix_md_path}")

    return fix_plan


def stage_fix(novel_dir: Path, chapter: int, title: str) -> bool:
    """审计修复阶段：分析审计失败原因，生成修复计划。"""
    fix_plan = generate_fix_plan(novel_dir, chapter, title)
    if fix_plan is None:
        return True  # 审计已通过或无法生成计划

    # 更新 passport
    passport = load_passport(novel_dir, chapter, title, find_chapter_file(novel_dir, chapter))
    passport["pipeline"]["fix_plan"] = "generated"
    passport["inputs"]["fix_plan"] = f"素材/fix_plan_ch{chapter:03d}.json"
    save_passport(novel_dir, chapter, passport)

    print(f"\n{'=' * 50}")
    print(f"修复计划摘要:")
    print(f"  总问题数: {fix_plan['total_issues']}")
    print(f"  高优先级: {fix_plan['high_priority']}")
    for action in fix_plan["actions"]:
        icon = {"high": "!!", "medium": "!", "low": "-"}.get(action.get("priority", ""), "?")
        print(f"  [{icon}] {action['description']}")
    print(f"{'=' * 50}")
    print(f"\n下一步: 根据修复计划修改正文，然后重跑 post:")
    print(f"  python write_pipeline.py post --novel-dir \"{novel_dir}\" --chapter {chapter} --title \"{title}\"")

    return False


# ============================================================
# P1: 阶段治理审计（每 N 章自动触发）
# ============================================================

GOVERNANCE_INTERVAL = 20  # 每20章触发一次


def governance_check(novel_dir: Path, chapter: int) -> bool:
    """阶段治理审计：每 N 章触发一次全量审计，生成趋势报告。

    检查：
    1. 累计字数/章节趋势
    2. 审计通过率趋势
    3. AI 词/对话比/风格漂移的跨章趋势
    4. 角色出场频率变化
    5. 质量滑坡预警
    """
    if chapter < GOVERNANCE_INTERVAL or chapter % GOVERNANCE_INTERVAL != 0:
        return True  # 不触发

    print(f"\n{'=' * 60}")
    print(f"[GOVERNANCE] 第{chapter}章 — 触发阶段治理审计（每{GOVERNANCE_INTERVAL}章）")
    print(f"{'=' * 60}")

    # 统一读取层：兼容 legacy / wrapped 格式与多种目录命名
    audit_reports: list[dict[str, Any]] = [
        report
        for report in load_audit_all(novel_dir, upto=chapter)
        if isinstance(report.get("chapter"), int)
    ]

    if len(audit_reports) < 5:
        print(f"[INFO] 审计报告不足5份（当前{len(audit_reports)}份），跳过趋势分析。")
        return True

    # --- 趋势分析 ---
    trends: dict[str, Any] = {"chapter": chapter, "analyzed_chapters": len(audit_reports)}

    # 1. 审计通过率
    pass_count = sum(1 for r in audit_reports if r.get("status") == "pass")
    trends["audit_pass_rate"] = round(pass_count / len(audit_reports), 3)

    # 2. AI 词趋势
    ai_trend: list[dict[str, Any]] = [
        {"chapter": r["chapter"], "ai_word_count": int(r.get("ai_word_count", 0))}
        for r in audit_reports
    ]
    trends["ai_words_trend"] = ai_trend

    # 3. 对话比例趋势
    dialogue_trend: list[dict[str, Any]] = []
    for r in audit_reports:
        ratio = r.get("dialogue_ratio")
        if isinstance(ratio, (int, float)):
            dialogue_trend.append({"chapter": r["chapter"], "ratio": round(float(ratio), 3)})
    trends["dialogue_ratio_trend"] = dialogue_trend

    # 4. 字数趋势
    word_trend: list[dict[str, Any]] = []
    for r in audit_reports:
        count = r.get("word_count")
        if isinstance(count, int):
            word_trend.append({"chapter": r["chapter"], "word_count": count})
    trends["word_count_trend"] = word_trend

    # --- 滑坡检测 ---
    warnings: list[str] = []

    # 最近5章通过率
    recent = audit_reports[-5:]
    recent_pass = sum(1 for r in recent if r.get("status") == "pass")
    if recent_pass < 3:
        warnings.append(f"⚠️ 最近5章审计通过率 {recent_pass}/5，质量滑坡风险")

    # AI 词回升
    if len(ai_trend) >= 10:
        first_half = [x["ai_word_count"] for x in ai_trend[:len(ai_trend) // 2]]
        second_half = [x["ai_word_count"] for x in ai_trend[len(ai_trend) // 2:]]
        avg_first = sum(first_half) / len(first_half) if first_half else 0
        avg_second = sum(second_half) / len(second_half) if second_half else 0
        if avg_second > avg_first * 1.5 and avg_second > 3:
            warnings.append(f"⚠️ AI 词密度回升: 前半 {avg_first:.1f} → 后半 {avg_second:.1f}")

    # 对话比例异常
    if dialogue_trend:
        recent_dialogue = [x["ratio"] for x in dialogue_trend[-5:]]
        avg_recent = sum(recent_dialogue) / len(recent_dialogue)
        if avg_recent < 0.15:
            warnings.append(f"⚠️ 最近5章对话比例 {avg_recent:.0%} 过低，可能变成纯叙述")
        elif avg_recent > 0.60:
            warnings.append(f"⚠️ 最近5章对话比例 {avg_recent:.0%} 过高，可能缺乏描写")

    # 字数缩水
    if word_trend and len(word_trend) >= 5:
        recent_words = [x["word_count"] for x in word_trend[-5:]]
        avg_recent = sum(recent_words) / len(recent_words)
        overall_avg = sum(x["word_count"] for x in word_trend) / len(word_trend)
        if avg_recent < overall_avg * 0.7:
            warnings.append(f"⚠️ 最近5章平均字数 {avg_recent:.0f}，低于整体均值 {overall_avg:.0f} 的 70%")

    trends["warnings"] = warnings

    # --- 保存报告 ---
    gov_report_path = novel_dir / "素材" / f"governance_ch{chapter:03d}.json"
    save_json(gov_report_path, trends)

    # 可读报告
    gov_md_path = novel_dir / "素材" / f"governance_ch{chapter:03d}.md"
    md_lines = [
        f"# 阶段治理报告 — 第{chapter}章",
        f"\n> 分析范围: 第1-{chapter}章 ({len(audit_reports)} 份审计报告)",
        f"> 生成时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## 核心指标",
        f"- 审计通过率: **{trends['audit_pass_rate']:.0%}**",
    ]

    if word_trend:
        total_words = sum(x["word_count"] for x in word_trend)
        md_lines.append(f"- 累计字数: **{total_words:,}**")
        md_lines.append(f"- 章均字数: **{total_words // len(word_trend):,}**")

    if dialogue_trend:
        avg_d = sum(x["ratio"] for x in dialogue_trend) / len(dialogue_trend)
        md_lines.append(f"- 平均对话比例: **{avg_d:.0%}**")

    if warnings:
        md_lines.append("\n## 预警")
        for w in warnings:
            md_lines.append(f"- {w}")
    else:
        md_lines.append("\n## 预警\n- 无预警，质量稳定 ✅")

    # 趋势摘要
    if ai_trend:
        md_lines.append("\n## AI 词趋势")
        for item in ai_trend[-10:]:
            bar = "█" * min(item["ai_word_count"], 20)
            md_lines.append(f"  第{item['chapter']:3d}章: {bar} {item['ai_word_count']}")

    gov_md_path.write_text("\n".join(md_lines), encoding="utf-8")

    print(f"\n[GOVERNANCE] 报告已保存:")
    print(f"  JSON: {gov_report_path}")
    print(f"  Markdown: {gov_md_path}")

    if warnings:
        print(f"\n[GOVERNANCE] ⚠️ {len(warnings)} 项预警:")
        for w in warnings:
            print(f"  {w}")
    else:
        print("\n[GOVERNANCE] ✅ 质量稳定，无预警")

    return len(warnings) == 0


def stage_act_summary(novel_dir: Path, volume: int, memory_dir: Path) -> bool:
    """聚合指定卷的所有章节摘要，生成卷级摘要并更新 novel_state.json。"""
    import json

    summary_files = sorted((novel_dir / "摘要").glob("chapter_*_summary.json"))
    if not summary_files:
        print("[WARN] 未找到任何章节摘要，跳过卷级摘要生成。", file=sys.stderr)
        return False

    chapters_data: list[dict[str, Any]] = []
    total_words = 0
    for sf in summary_files:
        data = load_json(sf, {})
        if not isinstance(data, dict):
            continue
        ch_num = data.get("chapter_number") or data.get("chapter")
        if ch_num is None:
            # 从文件名推断
            import re
            m = re.search(r"chapter_(\d+)_summary", sf.name)
            ch_num = int(m.group(1)) if m else 0
        chapters_data.append({
            "chapter": int(ch_num),
            "title": data.get("title", ""),
            "summary": data.get("summary", data.get("plot_summary", "")),
            "key_events": data.get("key_events", []),
            "word_count": data.get("word_count", 0),
        })
        total_words += int(data.get("word_count", 0) or 0)

    if not chapters_data:
        print("[WARN] 章节摘要数据为空，跳过。", file=sys.stderr)
        return False

    # 生成卷级摘要
    act_summary: dict[str, Any] = {
        "volume": volume,
        "chapter_count": len(chapters_data),
        "total_word_count": total_words,
        "chapters": chapters_data,
        "generated_at": now_iso(),
    }

    # 尝试提取卷级主题（从章节摘要中聚合）
    all_events: list[str] = []
    for ch in chapters_data:
        events = ch.get("key_events", [])
        if isinstance(events, list):
            all_events.extend(str(e) for e in events)
    if all_events:
        act_summary["aggregated_key_events"] = all_events

    act_path = novel_dir / "摘要" / f"act_{volume:02d}_summary.json"
    save_json(act_path, act_summary)
    print(f"[OK] 卷级摘要已生成: {act_path}")

    # 更新 novel_state.json
    state_path = novel_dir / "novel_state.json"
    state = load_json(state_path, {})
    if not isinstance(state, dict):
        state = {}
    state.setdefault("act_summaries", {})
    state["act_summaries"][f"vol_{volume:02d}"] = {
        "path": rel(act_path, novel_dir),
        "chapter_count": len(chapters_data),
        "total_word_count": total_words,
        "updated_at": act_summary["generated_at"],
    }
    state["updated_at"] = act_summary["generated_at"]
    save_json(state_path, state)
    print(f"[OK] novel_state.json 已更新卷 {volume} 摘要引用")

    # 同步到记忆系统
    memory_script = MEMORY_SCRIPT
    if memory_script.exists() and memory_dir.exists():
        # 把卷级摘要也作为"章节"同步，chapter号用 volume*1000 标记
        sync_cmd = [
            sys.executable,
            str(memory_script),
            "sync-chapter",
            "--input",
            str(act_path),
            "--memory-dir",
            str(memory_dir),
        ]
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        result = subprocess.run(sync_cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=workspace_root(), env=env)
        if result.returncode == 0:
            print("[OK] 卷级摘要已同步到记忆系统")
        else:
            print(f"[WARN] 卷级摘要同步到记忆系统失败: {result.stderr}", file=sys.stderr)

    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="小说章节写作流水线")
    parser.add_argument("stage", choices=["pre", "post", "all", "fix", "act-summary"], help="pre=写前, post=写后, all=两者都跑, fix=生成修复计划, act-summary=卷级摘要")
    parser.add_argument("--novel-dir", required=True, help="小说项目目录")
    parser.add_argument("--chapter", type=int, default=0, help="章节号（pre/post/all 必填）")
    parser.add_argument("--title", default="", help="章节标题")
    parser.add_argument("--memory-dir", default="", help="记忆目录，默认 <novel-dir>/记忆")
    parser.add_argument("--answers-file", default="", help="9问答案 JSON 文件")
    parser.add_argument("--scene-plan", default="", help="可选场景计划 JSON，pre 通过后初始化场景 passport")
    parser.add_argument("--quality-mode", choices=["", *QUALITY_MODES], default="", help="质量模式：默认读取 novel_state，支持 deterministic/balanced/tribunal")
    parser.add_argument("--quality-review-report", default="", help="balanced/tribunal 模式使用的人工确认审稿报告 JSON")
    parser.add_argument("--volume", type=int, default=0, help="卷号（act-summary 必填）")
    parser.add_argument(
        "--phase",
        choices=["all", *POST_PHASES],
        default="all",
        help="post 阶段：all 或 audit/truth/quality/memory/commit，可单独重跑",
    )
    parser.add_argument("--allow-missing-memory", action="store_true", help="记忆包生成失败时不阻断 pre 阶段")
    parser.add_argument(
        "--strict-knowledge",
        action="store_true",
        help="知识包必读项或选中路由文件缺失时阻断 pre（也可在 novel_state.json 设置 knowledge_gate=strict）",
    )
    parser.add_argument(
        "--override-prev-audit",
        action="store_true",
        help="跳过'上一章必须 audit pass'门禁（必须同时提供 --override-reason）",
    )
    parser.add_argument(
        "--override-reason",
        default="",
        help="跳过门禁的理由，会写入 novel_state.override_debt 留痕",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="commit 成功后不生成章节快照（默认备份正文/设定/摘要/记忆/状态/commit）",
    )
    args = parser.parse_args()

    try:
        workspace_state = wc.require_confirmed(workspace_root())
    except wc.WorkspaceConfirmationError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    if workspace_state.get("auto_confirmed"):
        print("[OK] 已为存量工作区补写确认标记")

    if args.stage == "act-summary":
        if not args.volume:
            print("[ERROR] act-summary 需要指定 --volume", file=sys.stderr)
            return 1
        novel_dir = Path(args.novel_dir) if Path(args.novel_dir).is_absolute() else workspace_root() / args.novel_dir
        memory_dir = Path(args.memory_dir) if args.memory_dir else find_memory_dir(novel_dir)
        return 0 if stage_act_summary(novel_dir, args.volume, memory_dir) else 1

    if args.stage in {"pre", "post", "all", "fix"} and not args.chapter:
        print("[ERROR] pre/post/all/fix 需要指定 --chapter", file=sys.stderr)
        return 1

    if args.stage == "fix":
        novel_dir = resolve_path(args.novel_dir)
        title = args.title or f"第{args.chapter}章"
        return 0 if stage_fix(novel_dir, args.chapter, title) else 1

    ok = True
    if args.stage in {"pre", "all"}:
        ok = stage_pre(args) and ok
    if args.stage in {"post", "all"}:
        ok = stage_post(args) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
