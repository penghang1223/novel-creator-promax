#!/usr/bin/env python3
"""
项目自检脚本

检查项：
  1. 必读记忆文件存在性
  2. 核心脚本路径可执行性
  3. 密钥是否误提交到 git
  4. README 示例是否违反禁词（"默"字人名）
  5. novel_output 是否正确忽略
  6. AGENTS.md 路径漂移（.Codex 残留）
  7. SKILL.md 命令路径正确性
  8. 临时脚本是否还在根目录
  9. 发布目录结构完整性
  10. SKILL.md frontmatter 格式
  11. 引用文件存在性
  12. 功能编号一致性（CLAUDE.md vs SKILL.md）
  13. agents/openai.yaml 存在性
  14. novel_creation_promax skill 自检
  15. 项目状态/管理契约与记忆目录一致性

用法:
    python tools/health_check.py
"""

import os
import re
import subprocess
import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from novel_creation_promax.core.jsonio import load_json
from novel_creation_promax.core.knowledge_routes import load_routes
from novel_creation_promax.core.project_registry import build_registry

ERRORS = []
WARNINGS = []


def error(msg):
    ERRORS.append(msg)
    print(f"  [FAIL] {msg}")


def warning(msg):
    WARNINGS.append(msg)
    print(f"  [WARN] {msg}")


def ok(msg):
    print(f"  [OK]   {msg}")


def safe_print(text):
    print(str(text).encode(sys.stdout.encoding or "utf-8", errors="replace").decode(sys.stdout.encoding or "utf-8", errors="replace"))


def check_memory_files():
    print("\n[1/18] 必读记忆文件")
    files = [
        "MEMORY.md",
        ".claude/memory/decisions/preferences.md",
        ".claude/memory/active_novels/progress.md",
        ".claude/memory/feedback/corrections.md",
        ".claude/memory/feedback/no-mer-names.md",
    ]
    for f in files:
        path = PROJECT_ROOT / f
        if path.exists():
            ok(f"{f}")
        else:
            error(f"缺失: {f}")


def check_scripts():
    print("\n[2/18] 核心脚本可执行性")
    scripts = [
        "novel_creation_promax/scripts/generate_cover.py",
        "novel_creation_promax/scripts/pre_write_check.py",
        "novel_creation_promax/scripts/post_write_audit.py",
        "novel_creation_promax/scripts/audit_pipeline.py",
        "novel_creation_promax/scripts/project_bootstrap_pipeline.py",
        "novel_creation_promax/scripts/write_pipeline.py",
        "novel_creation_promax/scripts/skill_health_check.py",
        "novel_creation_promax/scripts/name_generator.py",
        "novel_creation_promax/novel-memory-pro/scripts/memory_manager.py",
        "novel_creation_promax/scripts/style_dna_extractor.py",
        "novel_creation_promax/scripts/style_calibrator.py",
        "novel_creation_promax/scripts/plot_continuity_checker.py",
        "scripts/sync_to_fanqie.py",
        "tools/file_reference_counter.py",
        "tools/archive_knowledge.py",
        "tools/knowledge_base_audit.py",
        "tools/align_project_id.py",
        "tools/build_project_registry.py",
        "tools/knowledge_routes_check.py",
        "tools/knowledge_lint.py",
    ]
    for s in scripts:
        path = PROJECT_ROOT / s
        if path.exists():
            ok(f"{s}")
        else:
            error(f"缺失: {s}")


SECRET_FILE_DENYLIST = [
    "config.toml",
    "cc-connect-config.toml",
    ".claude/settings.local.json",
    ".mcp.json",
    ".env",
]

# 全仓扫描：只匹配"看起来像真实凭据"的字面量，避免误伤变量名/文档。
# 注意：git grep 使用 POSIX ERE，不支持 (?...) 非捕获组与 \b。
SECRET_PATTERNS = {
    "飞书 app_secret 明文": r"""(app_?secret|appSecret)["']?[[:space:]]*[:=][[:space:]]*["'][A-Za-z0-9_-]{16,}["']""",
    "飞书 App ID 明文": r"""cli_[a-z0-9]{16}""",
    "OpenAI 风格 key": r"""(^|[^A-Za-z0-9])sk-[A-Za-z0-9]{20,}""",
    "GitHub token": r"""(^|[^A-Za-z0-9])(ghp|gho|ghs)_[A-Za-z0-9]{20,}""",
    "AWS access key": r"""AKIA[A-Z0-9]{16}""",
    "明文密码": r"""(password|passwd|pwd)["']?[[:space:]]*[:=][[:space:]]*["'][^"'{}$<>]{8,}["']""",
}

SECRET_FALSE_POSITIVE_MARKERS = (
    "example", "your_", "YOUR_", "${", "$FEISHU", "<", ">",
    "xxxx", "XXXX", "****", "占位", "示例", "placeholder",
)


def _is_secret_false_positive(line: str) -> bool:
    lowered = line.lower()
    return any(marker.lower() in lowered for marker in SECRET_FALSE_POSITIVE_MARKERS)


def check_secrets_in_git():
    print("\n[3/18] 密钥误提交检查")
    for name in SECRET_FILE_DENYLIST:
        result = subprocess.run(
            ["git", "ls-files", name],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        if result.stdout.strip():
            error(f"{name} 仍在 git 跟踪中（可能含明文密钥），运行 git rm --cached")
        else:
            ok(f"{name} 未入库")

    scanned = 0
    for label, pattern in SECRET_PATTERNS.items():
        result = subprocess.run(
            ["git", "grep", "-nI", "-E", "-e", pattern],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        if result.returncode not in (0, 1):
            warning(f"{label} 扫描失败: {result.stderr.strip()[:120]}")
            continue
        hits = [
            line for line in result.stdout.splitlines()
            if line.strip() and not _is_secret_false_positive(line)
        ]
        scanned += 1
        if hits:
            error(f"{label}: 发现 {len(hits)} 处疑似明文")
            for line in hits[:5]:
                print(f"         {line[:160]}")
        else:
            ok(f"{label}: 无命中")
    if scanned == 0:
        warning("密钥正则扫描未执行成功")


def check_readme_banned_words():
    print("\n[4/18] README 禁词检查")
    readme = PROJECT_ROOT / "README.md"
    if not readme.exists():
        error("README.md 不存在")
        return

    content = readme.read_text(encoding="utf-8")
    # 检查是否包含"默"字作为人名的一部分
    # 简单检查：引号/书名号内或作为独立词出现的"默"
    patterns = [
        r'["\'][^"\'\n]*默[^"\'\n]*["\']',  # 单行引号内
        r'叫\s*\w*默\w*',               # "叫 xxx默xxx"
        r'主角叫[^，。\n]*默',           # "主角叫...默"
    ]
    found = False
    for pat in patterns:
        matches = re.findall(pat, content)
        for m in matches:
            if "默" in m:
                warning(f"README 中疑似含'默'字人名: {m}")
                found = True
    if not found:
        ok("README 未检测到含'默'字人名")


def check_gitignore():
    print("\n[5/18] .gitignore 检查")
    gitignore = PROJECT_ROOT / ".gitignore"
    if not gitignore.exists():
        error(".gitignore 不存在")
        return

    content = gitignore.read_text(encoding="utf-8")
    required = [".env", ".env.*", "config.toml", "cc-connect-config.toml"]
    for item in required:
        if item in content:
            ok(f"{item} 已忽略")
        else:
            error(f"{item} 未在 .gitignore 中")

    active_novel_output_pattern = re.search(r"(?m)^[^#\n]*novel_output/", content)
    if active_novel_output_pattern:
        error("novel_output/ 不应被 .gitignore 忽略")
    else:
        ok("novel_output/ 未被 .gitignore 忽略")


def check_agents_paths():
    print("\n[6/18] AGENTS.md 路径漂移检查")
    agents = PROJECT_ROOT / "AGENTS.md"
    if not agents.exists():
        error("AGENTS.md 不存在")
        return

    content = agents.read_text(encoding="utf-8")
    if ".Codex" in content:
        error("AGENTS.md 中仍有 .Codex 路径残留")
    else:
        ok("AGENTS.md 无 .Codex 残留")


def check_skill_paths():
    print("\n[7/18] SKILL.md 命令路径检查")
    skill = PROJECT_ROOT / "novel_creation_promax" / "SKILL.md"
    if not skill.exists():
        error("SKILL.md 不存在")
        return

    content = skill.read_text(encoding="utf-8")
    # 检查是否还有错误路径（不以 novel_creation_promax/ 开头的 scripts/xxx.py）
    bad_patterns = [
        r'python scripts/(?!sync_to_fanqie)',
        r'`scripts/[^`]+\.py`',
    ]
    found = False
    for pat in bad_patterns:
        matches = re.findall(pat, content)
        for m in matches:
            warning(f"SKILL.md 中疑似错误路径: {m}")
            found = True
    if not found:
        ok("SKILL.md 命令路径正确")


def check_root_temp_scripts():
    print("\n[8/18] 根目录临时脚本检查")
    temp_patterns = ["debug_*.py", "tmp_*.py"]
    found = False
    for pat in temp_patterns:
        for f in PROJECT_ROOT.glob(pat):
            error(f"根目录存在临时脚本: {f.name}")
            found = True
    if not found:
        ok("根目录无临时脚本")


def check_publish_dirs():
    print("\n[9/18] 发布目录结构检查")
    platforms = ["auto_publish/fanqie_auto_publish", "auto_publish/qidian_auto_publish", "auto_publish/zhihu_auto_publish", "auto_publish/qimao_auto_publish"]
    for p in platforms:
        path = PROJECT_ROOT / p
        if not path.exists():
            error(f"{p}/ 目录不存在")
            continue
        if not path.is_dir():
            error(f"{p} 不是目录（可能是损坏的链接）")
            continue
        readme = path / "README.md"
        if readme.exists():
            ok(f"{p}/ 结构正常")
        else:
            warning(f"{p}/ 缺少 README.md")

    # 检查 publish_system 是否还存在
    ps = PROJECT_ROOT / "publish_system"
    if ps.exists():
        warning("publish_system/ 目录仍存在（建议删除或合并）")
    else:
        ok("publish_system/ 已清理")


def check_frontmatter():
    print("\n[10/18] SKILL.md frontmatter 格式")
    skill = PROJECT_ROOT / "novel_creation_promax" / "SKILL.md"
    if not skill.exists():
        error("SKILL.md 不存在")
        return

    content = skill.read_text(encoding="utf-8")
    if content.startswith("---"):
        ok("SKILL.md frontmatter 格式正确（有 --- 包裹）")
    else:
        error("SKILL.md frontmatter 缺少 --- 包裹")

    # 也检查 novel-memory-pro/SKILL.md
    mm_skill = PROJECT_ROOT / "novel_creation_promax" / "novel-memory-pro" / "SKILL.md"
    if mm_skill.exists():
        mm_content = mm_skill.read_text(encoding="utf-8")
        if mm_content.startswith("---"):
            ok("novel-memory-pro/SKILL.md frontmatter 格式正确")
        else:
            error("novel-memory-pro/SKILL.md frontmatter 缺少 --- 包裹")


def check_references():
    print("\n[11/18] 引用文件存在性检查")
    skill = PROJECT_ROOT / "novel_creation_promax" / "SKILL.md"
    if not skill.exists():
        error("SKILL.md 不存在")
        return

    content = skill.read_text(encoding="utf-8")
    refs = set()
    for match in re.finditer(r"\[[^\]]+\]\(([^)]+)\)", content):
        refs.add(match.group(1))
    for match in re.finditer(r"`([^`\n]+)`", content):
        value = match.group(1)
        if value.startswith("python "):
            continue
        if value.startswith(("novel_creation_promax/", "references/", "docs/", "assets/", "novel-memory-pro/", "review-skill/", "knowledge_base/")):
            refs.add(value)

    missing = 0
    checked = 0
    for ref_path in sorted(refs):
        if '{' in ref_path or '*' in ref_path or "..." in ref_path:
            continue
        if ref_path.startswith(("http://", "https://")):
            continue
        if ref_path in {"novel_state.json"}:
            continue
        if ref_path.startswith("novel_creation_promax/"):
            full_path = PROJECT_ROOT / ref_path
        elif ref_path.startswith(("references/", "docs/", "assets/", "novel-memory-pro/", "review-skill/")):
            full_path = PROJECT_ROOT / "novel_creation_promax" / ref_path
        elif ref_path.startswith("knowledge_base/"):
            full_path = PROJECT_ROOT / ref_path
        else:
            continue
        checked += 1
        if not full_path.exists():
            warning(f"引用文件不存在: {ref_path}")
            missing += 1

    if missing == 0:
        ok(f"所有 {checked} 个引用文件检查通过")
    else:
        ok(f"引用检查完成: {checked - missing}/{checked} 存在")


def check_numbering_consistency():
    print("\n[12/18] 功能编号一致性检查")
    claude = PROJECT_ROOT / "CLAUDE.md"
    registry = PROJECT_ROOT / "novel_creation_promax" / "MODE_REGISTRY.md"

    if not claude.exists() or not registry.exists():
        error("CLAUDE.md 或 MODE_REGISTRY.md 不存在")
        return

    claude_content = claude.read_text(encoding="utf-8")
    registry_content = registry.read_text(encoding="utf-8")

    # 提取关键功能的编号
    # CLAUDE.md: "正文润色 [N]"（行为规则常驻，编号以 MODE_REGISTRY 为准）
    claude_match = re.search(r'正文润色 \[(\d+)\].*审稿评估 \[(\d+)\].*短篇创作 \[(\d+)\]', claude_content)
    # MODE_REGISTRY.md 表格行: "| 8 | polish | 正文润色 | ..."
    registry_match = re.search(r'\|\s*(\d+)\s*\|[^|\n]*\|\s*正文润色\s*\|', registry_content)

    if claude_match and registry_match:
        claude_nums = (int(claude_match.group(1)), int(claude_match.group(2)), int(claude_match.group(3)))
        registry_num = int(registry_match.group(1))
        if claude_nums[0] == registry_num:
            ok(f"正文润色编号一致: [{registry_num}]")
        else:
            error(f"正文润色编号不一致: CLAUDE.md=[{claude_nums[0]}], MODE_REGISTRY=[{registry_num}]")
    else:
        warning("无法提取功能编号进行对比")


def check_agents_yaml():
    print("\n[13/18] agents/openai.yaml 检查")
    agents_yaml = PROJECT_ROOT / "novel_creation_promax" / "agents" / "openai.yaml"
    if agents_yaml.exists():
        ok("agents/openai.yaml 存在")
    else:
        warning("agents/openai.yaml 不存在（如需注册 Codex skill 建议补充）")


def check_skill_health_script():
    print("\n[14/18] novel_creation_promax skill 自检")
    script = PROJECT_ROOT / "novel_creation_promax" / "scripts" / "skill_health_check.py"
    if not script.exists():
        error("novel_creation_promax/scripts/skill_health_check.py 不存在")
        return
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    if result.stdout:
        safe_print(result.stdout)
    if result.stderr:
        print(result.stderr.encode(sys.stderr.encoding or "utf-8", errors="replace").decode(sys.stderr.encoding or "utf-8", errors="replace"), file=sys.stderr)
    if result.returncode == 0:
        ok("skill 自检通过")
    else:
        error(f"skill 自检失败（exit {result.returncode}）")


def check_core_package():
    print("\n[15/18] core 共享包检查")
    required = [
        "novel_creation_promax/core/__init__.py",
        "novel_creation_promax/core/jsonio.py",
        "novel_creation_promax/core/paths.py",
        "novel_creation_promax/core/passport.py",
        "novel_creation_promax/core/knowledge_routes.py",
        "novel_creation_promax/core/project_registry.py",
    ]
    for item in required:
        if (PROJECT_ROOT / item).exists():
            ok(item)
        else:
            error(f"缺失: {item}")


def check_knowledge_routes():
    print("\n[16/18] 机器可读知识路由检查")
    routes = load_routes(PROJECT_ROOT)
    if not routes:
        error("knowledge_base/_ROUTES.json 不存在或无法读取")
        return
    missing = []
    checked = 0
    for item in routes.get("required", []):
        path = item.get("path", "")
        if not path or "{" in path or "}" in path:
            continue
        checked += 1
        if not (PROJECT_ROOT / path).exists():
            missing.append(path)
    for route in routes.get("routes", []):
        for path in route.get("files", []):
            if "{" in path or "}" in path:
                continue
            checked += 1
            if not (PROJECT_ROOT / path).exists():
                missing.append(path)
    for item in routes.get("evaluations", []):
        path = item.get("file", "")
        if path:
            checked += 1
            if not (PROJECT_ROOT / path).exists():
                missing.append(path)
    if missing:
        for path in missing:
            error(f"知识路由引用不存在: {path}")
    else:
        ok(f"知识路由引用检查通过（{checked} 项）")


def check_knowledge_base_structure():
    print("\n[20/20] 知识库目录架构检查")
    try:
        from tools.knowledge_base_audit import audit
        report = audit()
    except Exception as exc:  # noqa: BLE001
        error(f"知识库架构审计失败: {exc}")
        return
    for message in report.get("errors", []):
        error(message)
    for message in report.get("warnings", []):
        warning(message)
    ok(
        f"知识库结构可解析: files={report.get('file_count')}, "
        f"inbox={report.get('inbox_count')}, "
        f"incomplete_projects={len(report.get('incomplete_projects', []))}"
    )


def check_project_registry_builder():
    print("\n[17/18] 项目注册表生成检查")
    registry = build_registry(PROJECT_ROOT)
    summary = registry.get("summary", {})
    if summary.get("project_count", 0) > 0:
        message = (
            "registry 可生成: "
            f"projects={summary.get('project_count')}, "
            f"outputs={summary.get('novel_output_count')}, "
            f"80_Projects={summary.get('knowledge_project_count')}, "
            f"issues={summary.get('issue_count')}"
        )
        if summary.get("issue_count", 0):
            warning(message)
        else:
            ok(message)
    else:
        warning("registry 生成结果为空")


def check_project_contract():
    print("\n[19/19] 项目状态与目录契约")
    output_root = PROJECT_ROOT / "novel_output"
    if not output_root.exists():
        warning("novel_output 不存在，跳过项目契约检查")
        return

    management_files = ("项目章程.md", "风险登记表.md")
    missing_management = []
    legacy_state = []
    duplicate_memory = []
    ignored_platforms = {"素材", "_workspace", "covers", "archive", "uploaded", "short_uploaded"}
    for platform_dir in sorted(
        path for path in output_root.iterdir() if path.is_dir() and path.name not in ignored_platforms
    ):
        for novel_dir in sorted(path for path in platform_dir.iterdir() if path.is_dir()):
            if novel_dir.name in {"素材", "_workspace", "covers", "archive", "uploaded", "short_uploaded"}:
                continue
            missing = [name for name in management_files if not (novel_dir / name).is_file()]
            if missing:
                missing_management.append((novel_dir, missing))
            state_path = novel_dir / "novel_state.json"
            if state_path.exists():
                state = load_json(state_path, {})
                if not isinstance(state, dict) or state.get("schema_version") != "2.0":
                    legacy_state.append(novel_dir)
            if (novel_dir / "memory").is_dir() and (novel_dir / "记忆").is_dir():
                duplicate_memory.append(novel_dir)

    if missing_management:
        warning(f"{len(missing_management)} 个项目缺少项目章程/风险登记表，可运行 tools/backfill_project_management.py --all --apply 补齐")
    else:
        ok("所有 novel_output 项目具备管理文件")
    if legacy_state:
        warning(f"{len(legacy_state)} 个项目仍未迁移到 novel_state v2，可运行 tools/normalize_project_state.py --all --apply")
    else:
        ok("所有现有 novel_state.json 已是 v2")
    if duplicate_memory:
        warning(f"{len(duplicate_memory)} 个项目同时存在 memory 与 记忆，可运行 tools/merge_memory_aliases.py --all --apply")
    else:
        ok("记忆目录别名无重复")

    try:
        from novel_output_audit import audit as audit_novel_output

        output_audit = audit_novel_output(output_root)
        summary = output_audit["summary"]
        if summary["errors"]:
            warning(
                "novel_output 结构存在问题: "
                f"重复项目 {summary['duplicate_titles']} 个，"
                f"正文混入产物 {summary['body_artifacts']} 个，"
                f"根目录备份 {summary['state_backups']} 个；"
                "可先运行 tools/normalize_novel_output.py --json 预览"
            )
        elif summary["warnings"]:
            warning(
                "novel_output 仍有结构提醒: "
                f"正文混入产物 {summary['body_artifacts']} 个，"
                f"根目录备份 {summary['state_backups']} 个"
            )
        else:
            ok("novel_output 结构通过审计")
    except Exception as exc:  # noqa: BLE001
        warning(f"novel_output 结构审计不可用: {exc}")


def check_audit_coverage():
    """审计覆盖率：暴露"写了但没审"的存量债务（警告级，不阻断）。"""
    print("\n[18/18] 审计覆盖率")
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    try:
        from novel_creation_promax.core.audit_schema import load_audit_all
        from novel_creation_promax.core.paths import list_chapter_files
    except Exception as exc:  # noqa: BLE001
        warning(f"无法导入 core 审计模块: {exc}")
        return

    total = 0
    audited = 0
    rows = []
    for platform_dir in sorted((PROJECT_ROOT / "novel_output").iterdir()):
        if not platform_dir.is_dir():
            continue
        for novel_dir in sorted(platform_dir.iterdir()):
            if not novel_dir.is_dir() or not (novel_dir / "正文").is_dir():
                continue
            chapters = list_chapter_files(novel_dir)
            if not chapters:
                continue
            reports = {item["chapter"] for item in load_audit_all(novel_dir)}
            chapter_count = len(chapters)
            audited_count = sum(1 for chapter, _ in chapters if chapter in reports)
            total += chapter_count
            audited += audited_count
            rows.append((str(novel_dir.relative_to(PROJECT_ROOT)), chapter_count, audited_count))

    if total == 0:
        warning("未找到任何章节")
        return

    rate = audited / total
    message = f"全库审计覆盖率 {audited}/{total} ({rate:.1%})"
    if rate >= 0.8:
        ok(message)
    else:
        warning(message)

    backlog = [r for r in rows if r[2] == 0 and r[1] >= 5]
    if backlog:
        warning(f"{len(backlog)} 个长篇项目完全无审计（存量债务）")
        for path, chapter_count, _ in backlog[:8]:
            print(f"         {path} ({chapter_count} 章)")


def main():
    print("=" * 50)
    print("小说创作 Pro Max — 项目健康检查")
    print("=" * 50)

    check_memory_files()
    check_scripts()
    check_secrets_in_git()
    check_readme_banned_words()
    check_gitignore()
    check_agents_paths()
    check_skill_paths()
    check_root_temp_scripts()
    check_publish_dirs()
    check_frontmatter()
    check_references()
    check_numbering_consistency()
    check_agents_yaml()
    check_skill_health_script()
    check_core_package()
    check_knowledge_routes()
    check_project_registry_builder()
    check_audit_coverage()
    check_project_contract()
    check_knowledge_base_structure()

    print("\n" + "=" * 50)
    print(f"结果: {len(ERRORS)} 错误, {len(WARNINGS)} 警告")
    if ERRORS:
        print("\n错误项:")
        for e in ERRORS:
            print(f"  - {e}")
    if WARNINGS:
        print("\n警告项:")
        for w in WARNINGS:
            print(f"  - {w}")
    print("=" * 50)

    return 1 if ERRORS else 0


if __name__ == "__main__":
    sys.exit(main())
