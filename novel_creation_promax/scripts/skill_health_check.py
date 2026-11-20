#!/usr/bin/env python3
"""
novel_creation_promax skill 自检。

检查 skill 标准化、引用文件、模式编号、脚本路径和关键文档是否一致。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SKILL_ROOT = PROJECT_ROOT / "novel_creation_promax"
SUBSKILLS = (
    "novel-memory-pro",
    "review-skill",
    "project-planning",
    "publishing",
    "knowledge-ingestion",
)


class Check:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def ok(self, msg: str) -> None:
        print(f"[OK]   {msg}")

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)
        print(f"[WARN] {msg}")

    def fail(self, msg: str) -> None:
        self.errors.append(msg)
        print(f"[FAIL] {msg}")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def check_frontmatter(c: Check, path: Path) -> None:
    if not path.exists():
        c.fail(f"缺失 {path.relative_to(PROJECT_ROOT)}")
        return
    text = read_text(path)
    if not text.startswith("---\n"):
        c.fail(f"{path.relative_to(PROJECT_ROOT)} 缺少标准 frontmatter")
        return
    end = text.find("\n---", 4)
    if end == -1:
        c.fail(f"{path.relative_to(PROJECT_ROOT)} frontmatter 未闭合")
        return
    fm = text[4:end]
    if "name:" not in fm or "description:" not in fm:
        c.fail(f"{path.relative_to(PROJECT_ROOT)} frontmatter 缺少 name/description")
    else:
        c.ok(f"{path.relative_to(PROJECT_ROOT)} frontmatter")


def check_required_files(c: Check) -> None:
    files = [
        "SKILL.md",
        "MODE_REGISTRY.md",
        "agents/openai.yaml",
        "docs/ARCHITECTURE.md",
        "docs/PIPELINE.md",
        "docs/ARTIFACTS.md",
        "docs/DATA_ACCESS_LEVELS.md",
        "references/orchestrator.md",
        "references/trigger-rules.md",
        "references/knowledge-pack-workflow.md",
        "scripts/audit_pipeline.py",
        "scripts/pipeline_utils.py",
        "scripts/project_bootstrap_pipeline.py",
        "scripts/write_pipeline.py",
    ]
    for item in files:
        path = SKILL_ROOT / item
        if path.exists():
            c.ok(item)
        else:
            c.fail(f"缺失 {item}")
    for name in SUBSKILLS:
        path = SKILL_ROOT / name / "SKILL.md"
        if path.exists():
            c.ok(f"{name}/SKILL.md")
        else:
            c.fail(f"缺失 {name}/SKILL.md")


def extract_markdown_refs(text: str) -> list[str]:
    refs: list[str] = []
    for match in re.finditer(r"\[[^\]]+\]\(([^)]+)\)", text):
        refs.append(match.group(1))
    for match in re.finditer(r"`([^`]+)`", text):
        value = match.group(1)
        if "\n" in value:
            continue
        if value.startswith(("python ", "json", "text", "bash")):
            continue
        if (
            value.startswith(("novel_creation_promax/", "references/", "docs/", "assets/", "scripts/", "novel-memory-pro/", "review-skill/", "knowledge_base/", "skills/", "commands/", "hooks/", "tools/", "AGENTS.md", "CLAUDE.md"))
            or re.search(r"\.(md|json|yaml|py)$", value)
        ):
            refs.append(value)
    return refs


def resolve_ref(ref: str, source: Path) -> Path:
    ref = ref.split("#", 1)[0]
    if ref.startswith("novel_creation_promax/"):
        return PROJECT_ROOT / ref
    if ref.startswith("knowledge_base/"):
        return PROJECT_ROOT / ref
    if ref.startswith(("skills/", "commands/", "hooks/", "tools/")):
        return PROJECT_ROOT / ref
    if ref in {"AGENTS.md", "CLAUDE.md"}:
        return PROJECT_ROOT / ref
    candidates: list[Path] = []
    if ref.startswith("../"):
        candidates.append((source.parent / ref).resolve())
    elif ref.startswith(("references/", "docs/", "assets/", "scripts/")):
        candidates.extend([(source.parent / ref).resolve(), SKILL_ROOT / ref])
    elif ref.startswith((*SUBSKILLS,)):
        candidates.append(SKILL_ROOT / ref)
    else:
        candidates.extend(
            [
                (source.parent / ref).resolve(),
                SKILL_ROOT / ref,
                SKILL_ROOT / "scripts" / ref,
                SKILL_ROOT / "assets" / "templates" / ref,
            ]
        )
    return next((candidate for candidate in candidates if candidate.exists()), candidates[0])


def check_refs(c: Check, path: Path) -> None:
    text = read_text(path)
    checked = 0
    missing = 0
    for ref in sorted(set(extract_markdown_refs(text))):
        if any(token in ref for token in ["{", "}", "*", "..."]):
            continue
        if ref.startswith(("http://", "https://")):
            continue
        if ref in {
            "novel_state.json",
            "素材/project_bootstrap_gate.json",
            "chapter_summary.json",
            "project_bootstrap.json",
        } or ref.startswith("摘要/"):
            continue
        if " " in ref and not ref.endswith((".md", ".json", ".yaml", ".py")):
            continue
        target = resolve_ref(ref, path)
        checked += 1
        if not target.exists():
            c.warn(f"{path.relative_to(PROJECT_ROOT)} 引用不存在: {ref}")
            missing += 1
    if missing == 0:
        c.ok(f"{path.relative_to(PROJECT_ROOT)} 引用检查 {checked}/{checked}")


def parse_mode_ids(path: Path) -> dict[int, str]:
    ids: dict[int, str] = {}
    text = read_text(path)
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if not cells:
            continue
        try:
            mode_id = int(cells[0])
        except ValueError:
            continue
        ids[mode_id] = cells[2] if len(cells) > 2 else ""
    return ids


def check_mode_registry(c: Check) -> None:
    registry = SKILL_ROOT / "MODE_REGISTRY.md"
    skill = SKILL_ROOT / "SKILL.md"
    if not registry.exists() or not skill.exists():
        return
    mode_ids = parse_mode_ids(registry)
    expected = set(range(17))
    actual = set(mode_ids)
    if actual == expected:
        c.ok("MODE_REGISTRY mode_id 连续 0-16")
    else:
        c.fail(f"MODE_REGISTRY mode_id 不连续: {sorted(actual)}")

    skill_text = read_text(skill)
    if "MODE_REGISTRY.md" in skill_text:
        c.ok("SKILL.md 委托 MODE_REGISTRY 路由功能编号")
    else:
        c.fail("SKILL.md 缺少 MODE_REGISTRY 路由入口")


def check_skill_contracts(c: Check) -> None:
    main_skill = SKILL_ROOT / "SKILL.md"
    if not main_skill.exists():
        return
    main_text = read_text(main_skill)
    routes = {
        "project-planning/SKILL.md": "立项与大纲",
        "novel-memory-pro/SKILL.md": "记忆",
        "review-skill/SKILL.md": "审稿",
        "publishing/SKILL.md": "发布",
        "knowledge-ingestion/SKILL.md": "知识摄入",
        "references/orchestrator.md": "章节状态机",
    }
    for ref, label in routes.items():
        if ref in main_text:
            c.ok(f"主技能路由: {label}")
        else:
            c.fail(f"主技能缺少路由: {label} ({ref})")

    for name in SUBSKILLS:
        path = SKILL_ROOT / name / "SKILL.md"
        if not path.exists():
            continue
        text = read_text(path)
        if "## 边界" not in text:
            c.fail(f"{name}/SKILL.md 缺少职责边界")
        elif "## 禁止事项" not in text:
            c.fail(f"{name}/SKILL.md 缺少禁止事项")
        else:
            c.ok(f"{name}/SKILL.md 职责边界")


def check_bad_paths(c: Check) -> None:
    paths = [SKILL_ROOT / "SKILL.md", SKILL_ROOT / "references" / "orchestrator.md", SKILL_ROOT / "review-skill" / "SKILL.md"]
    bad_patterns = [
        (r"python scripts/(?!sync_to_fanqie)", "旧脚本路径 python scripts/"),
        (r"python novel-memory-pro/", "旧记忆路径 python novel-memory-pro/"),
        (r"`scripts/[^`]+\.py`", "裸 scripts/*.py 引用"),
    ]
    for path in paths:
        if not path.exists():
            continue
        text = read_text(path)
        for pattern, label in bad_patterns:
            matches = re.findall(pattern, text)
            if matches:
                c.warn(f"{path.relative_to(PROJECT_ROOT)} 存在 {label}: {len(matches)} 处")


def check_command_aliases(c: Check) -> None:
    plugin_commands = PROJECT_ROOT / "commands"
    if plugin_commands.is_dir():
        commands_dir = plugin_commands
        label = "commands"
        expected = [
            "init.md",
            "research.md",
            "idea.md",
            "plan.md",
            "outline.md",
            "write.md",
            "review.md",
            "polish.md",
            "memory.md",
            "publish.md",
            "audit.md",
            "doctor.md",
            "workflow.md",
        ]
    else:
        commands_dir = PROJECT_ROOT / ".claude" / "commands"
        label = ".claude/commands"
        expected = [
            "novel-plan.md",
            "novel-outline.md",
            "novel-write.md",
            "novel-audit.md",
            "novel-polish.md",
            "novel-memory.md",
            "novel-review.md",
            "novel-publish.md",
        ]
    for name in expected:
        path = commands_dir / name
        if path.exists():
            c.ok(f"{label}/{name}")
        else:
            c.fail(f"缺失 {label}/{name}")


def main() -> int:
    parser = argparse.ArgumentParser(description="novel_creation_promax skill 自检")
    parser.parse_args()

    c = Check()
    print("== frontmatter ==")
    check_frontmatter(c, SKILL_ROOT / "SKILL.md")
    for name in SUBSKILLS:
        check_frontmatter(c, SKILL_ROOT / name / "SKILL.md")

    print("\n== required files ==")
    check_required_files(c)

    print("\n== references ==")
    for file in [
        "SKILL.md",
        "MODE_REGISTRY.md",
        "docs/ARCHITECTURE.md",
        "docs/PIPELINE.md",
        "docs/ARTIFACTS.md",
        "docs/DATA_ACCESS_LEVELS.md",
        *[f"{name}/SKILL.md" for name in SUBSKILLS],
    ]:
        check_refs(c, SKILL_ROOT / file)

    print("\n== skill contracts ==")
    check_skill_contracts(c)

    print("\n== mode registry ==")
    check_mode_registry(c)

    print("\n== path drift ==")
    check_bad_paths(c)

    print("\n== command aliases ==")
    check_command_aliases(c)

    print("\n== result ==")
    print(f"errors={len(c.errors)} warnings={len(c.warnings)}")
    return 1 if c.errors else 0


if __name__ == "__main__":
    sys.exit(main())
