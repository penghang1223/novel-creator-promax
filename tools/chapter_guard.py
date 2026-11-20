#!/usr/bin/env python3
"""章节写作门禁（chapter guard）。

把"写了正文但没审计/没护照"从"靠自觉"变成"可被脚本判定"，并挂到
git pre-commit：**新增或修改的正文文件，必须已有对应审计报告**，
否则提交被拒。

三种用法：

    # 1) 全库体检（只报告，不阻断）
    python tools/chapter_guard.py

    # 2) 预提交门禁（只看本次暂存的正文文件，缺失即失败）
    python tools/chapter_guard.py --changed-only

    # 3) CI / 严格模式（全库覆盖率低于阈值即失败）
    python tools/chapter_guard.py --strict --min-rate 0.8

设计原则：历史存量不阻断提交（否则无法工作），只对"本次改动"硬失败。
存量债务用 --report 输出清单，配合 tools/reconcile_novel_state.py 与
tools/backfill_audits.py 逐步偿还。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from novel_creation_promax.core.audit_schema import find_audit_report, load_audit_all  # noqa: E402
from novel_creation_promax.core.chapter_commit import commit_path, verify_chapter_commit  # noqa: E402
from novel_creation_promax.core.passport import passport_path  # noqa: E402
from novel_creation_promax.core.paths import (  # noqa: E402
    CHAPTER_EXTENSIONS,
    infer_chapter_number,
    list_chapter_files,
)

DEFAULT_MIN_RATE = 0.8


def rel(path: Path) -> str:
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def novel_dir_of(chapter_file: Path) -> Path | None:
    """从 正文/ 下的文件反推小说目录。"""
    parts = chapter_file.parts
    for index, part in enumerate(parts):
        if part == "正文" and index > 0:
            return Path(*parts[:index])
    return None


def check_chapter(
    novel_dir: Path,
    chapter: int,
    chapter_file: Path,
    *,
    require_commit: bool = False,
) -> dict[str, Any]:
    audit = find_audit_report(novel_dir, chapter)
    passport = passport_path(novel_dir, chapter)
    summary = novel_dir / "摘要" / f"chapter_{chapter:03d}_summary.json"
    problems: list[str] = []
    warnings: list[str] = []
    if audit is None:
        problems.append("缺少审计报告")
    if not passport.exists():
        warnings.append("缺少章节护照 passport")
    if not summary.exists():
        warnings.append("缺少章节摘要 summary")
    commit_file = commit_path(novel_dir, chapter)
    if commit_file.exists():
        commit_ok, commit_detail = verify_chapter_commit(novel_dir, chapter)
        if not commit_ok:
            (problems if require_commit else warnings).append(commit_detail)
    elif require_commit:
        problems.append("缺少章节提交记录 commit")
    else:
        warnings.append("缺少章节提交记录 commit")
    return {
        "novel_dir": rel(novel_dir),
        "chapter": chapter,
        "file": rel(chapter_file),
        "audit": rel(audit) if audit else "",
        "commit": rel(commit_file) if commit_file.exists() else "",
        "problems": problems,
        "warnings": warnings,
    }


def staged_chapter_files() -> list[Path]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=AM", "-z"],
        capture_output=True,
        cwd=PROJECT_ROOT,
    )
    if result.returncode != 0:
        return []
    raw = result.stdout.decode("utf-8", errors="replace")
    files: list[Path] = []
    for name in raw.split("\0"):
        if not name:
            continue
        if "/正文/" not in name and not name.startswith("novel_output/"):
            continue
        path = PROJECT_ROOT / name
        if path.suffix.lower() in CHAPTER_EXTENSIONS and "/正文/" in name:
            files.append(path)
    return files


def iter_novel_dirs() -> list[Path]:
    """所有含 正文/ 的小说目录（不要求存在 novel_state.json）。"""
    dirs: list[Path] = []
    for platform_dir in sorted((PROJECT_ROOT / "novel_output").iterdir()):
        if not platform_dir.is_dir():
            continue
        for novel_dir in sorted(platform_dir.iterdir()):
            if novel_dir.is_dir() and (novel_dir / "正文").is_dir():
                dirs.append(novel_dir)
    return dirs


def scan_all() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for novel_dir in iter_novel_dirs():
        chapters = list_chapter_files(novel_dir)
        if not chapters:
            continue
        reports = {item["chapter"] for item in load_audit_all(novel_dir) if isinstance(item.get("chapter"), int)}
        missing = [chapter for chapter, _ in chapters if chapter not in reports]
        rows.append(
            {
                "novel_dir": rel(novel_dir),
                "chapters": len(chapters),
                "audited": len(chapters) - len(missing),
                "missing": missing,
                "rate": round((len(chapters) - len(missing)) / len(chapters), 4),
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="章节写作门禁：正文必须有审计报告")
    parser.add_argument("--changed-only", action="store_true", help="只检查 git 暂存的正文文件（pre-commit 用）")
    parser.add_argument("--strict", action="store_true", help="全库覆盖率低于阈值时返回非零")
    parser.add_argument("--min-rate", type=float, default=DEFAULT_MIN_RATE, help=f"严格模式阈值，默认 {DEFAULT_MIN_RATE}")
    parser.add_argument("--novel-dir", default="", help="只检查单个项目")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--limit", type=int, default=10, help="每项最多展示多少条")
    parser.add_argument("--require-commit", action="store_true", help="changed-only 模式要求章节提交记录有效")
    args = parser.parse_args()

    if args.changed_only:
        files = staged_chapter_files()
        if not files:
            print("[chapter-guard] 本次提交没有正文改动，跳过。")
            return 0
        results = []
        failed = False
        for path in files:
            novel_dir = novel_dir_of(path)
            chapter = infer_chapter_number(path)
            if novel_dir is None or chapter is None:
                results.append(
                    {"file": rel(path), "chapter": None, "problems": ["无法识别小说目录或章号"], "warnings": []}
                )
                continue
            result = check_chapter(novel_dir, chapter, path, require_commit=args.require_commit)
            results.append(result)
            if result["problems"]:
                failed = True

        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            for result in results:
                if result["problems"]:
                    print(f"[BLOCK] {result.get('file')} ch{result.get('chapter')}: {', '.join(result['problems'])}")
                elif result["warnings"]:
                    print(f"[WARN]  {result.get('file')} ch{result.get('chapter')}: {', '.join(result['warnings'])}")

        if failed:
            print("\n[chapter-guard] 提交被拒绝：新增/修改的正文缺少审计报告。", file=sys.stderr)
            print("[NEXT] 运行: python novel_creation_promax/scripts/write_pipeline.py post "
                  "--novel-dir <小说目录> --chapter <章号> --title <标题>", file=sys.stderr)
            print("[BYPASS] 确属例外时可用 git commit --no-verify（会跳过所有钩子）。", file=sys.stderr)
            return 1
        print("[chapter-guard] 通过：本次正文改动均有审计记录。")
        return 0

    # 全库模式
    if args.novel_dir:
        novel_dir = Path(args.novel_dir)
        if not novel_dir.is_absolute():
            novel_dir = PROJECT_ROOT / novel_dir
        chapters = list_chapter_files(novel_dir)
        reports = {item["chapter"] for item in load_audit_all(novel_dir) if isinstance(item.get("chapter"), int)}
        rows = [
            {
                "novel_dir": rel(novel_dir),
                "chapters": len(chapters),
                "audited": sum(1 for chapter, _ in chapters if chapter in reports),
                "missing": [chapter for chapter, _ in chapters if chapter not in reports],
                "rate": round(sum(1 for chapter, _ in chapters if chapter in reports) / len(chapters), 4)
                if chapters
                else 0.0,
            }
        ]
    else:
        rows = scan_all()

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        if args.strict:
            total = sum(row["chapters"] for row in rows)
            audited = sum(row["audited"] for row in rows)
            return 0 if total and audited / total >= args.min_rate else 1
        return 0

    total = sum(row["chapters"] for row in rows)
    audited = sum(row["audited"] for row in rows)
    rate = audited / total if total else 0.0

    print(f"{'项目':<45}{'章节':>6}{'已审计':>8}{'覆盖率':>8}")
    print("-" * 70)
    for row in sorted(rows, key=lambda item: item["rate"]):
        print(f"{row['novel_dir']:<45}{row['chapters']:>6}{row['audited']:>8}{row['rate']:>8.1%}")
    print("-" * 70)
    print(f"{'合计':<45}{total:>6}{audited:>8}{rate:>8.1%}")

    backlog = [row for row in rows if row["missing"]]
    if backlog:
        print(f"\n存量缺口（{len(backlog)} 个项目）：")
        for row in sorted(backlog, key=lambda item: -len(item["missing"]))[: args.limit]:
            preview = ", ".join(str(chapter) for chapter in row["missing"][:8])
            suffix = " …" if len(row["missing"]) > 8 else ""
            print(f"  {row['novel_dir']}: {len(row['missing'])} 章未审计 ch[{preview}{suffix}]")

    if args.strict:
        if total == 0:
            print("[strict] 未找到任何章节", file=sys.stderr)
            return 1
        if rate < args.min_rate:
            print(
                f"[strict] 审计覆盖率 {rate:.1%} 低于阈值 {args.min_rate:.0%}",
                file=sys.stderr,
            )
            return 1
        print(f"[strict] 通过：覆盖率 {rate:.1%} ≥ {args.min_rate:.0%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
