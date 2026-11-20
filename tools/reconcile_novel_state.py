#!/usr/bin/env python3
"""对账 novel_state.json 里声明的审计状态与磁盘上的真实审计报告。

背景：历史项目的 ``novel_state.chapters[].audit`` 是手工/生成时写死的，
不随真实审计增长而更新，出现了"43 章全标通过、实际只有 11 份审计报告"的
自证式数据。这会让覆盖率统计与门禁判断全部失真。

本工具只读真实审计文件（``core.audit_schema.load_audit``），把每章状态
重算为 ``pass`` / ``fail`` / ``missing``，默认 dry-run，``--apply`` 才写回，
写回前生成 ``novel_state.json.bak-<时间戳>`` 备份。

用法：
    python tools/reconcile_novel_state.py --novel-dir "novel_output/番茄/002_我发疯后全世界都正常了"
    python tools/reconcile_novel_state.py --novel-dir "..." --apply
    python tools/reconcile_novel_state.py --all --json
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from novel_creation_promax.core.audit_schema import load_audit  # noqa: E402
from novel_creation_promax.core.paths import list_chapter_files, rel  # noqa: E402

STATUS_LABELS = {"pass": "通过", "fail": "未通过", "missing": "未审计"}


def chapter_entries(state: dict[str, Any]) -> list[dict[str, Any]]:
    """把 chapters 的 list / dict 两种形态统一成可遍历的 entry 列表。"""
    chapters = state.get("chapters")
    entries: list[dict[str, Any]] = []
    if isinstance(chapters, list):
        for entry in chapters:
            if isinstance(entry, dict):
                entries.append(entry)
    elif isinstance(chapters, dict):
        for key in sorted(chapters):
            entry = chapters[key]
            if isinstance(entry, dict):
                entry.setdefault("number", int(key) if str(key).isdigit() else key)
                entries.append(entry)
    return entries


def entry_number(entry: dict[str, Any]) -> int | None:
    for key in ("number", "chapter", "index"):
        value = entry.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


def reconcile(novel_dir: Path, *, apply: bool = False) -> dict[str, Any]:
    state_path = novel_dir / "novel_state.json"
    if not state_path.exists():
        return {"novel_dir": str(novel_dir), "error": "novel_state.json 不存在"}

    state = json.loads(state_path.read_text(encoding="utf-8"))
    if not isinstance(state, dict):
        return {"novel_dir": str(novel_dir), "error": "novel_state.json 不是对象"}

    on_disk = {chapter for chapter, _ in list_chapter_files(novel_dir)}
    entries = chapter_entries(state)
    changes: list[dict[str, Any]] = []
    actual: dict[int, str] = {}

    for chapter in sorted(on_disk):
        report = load_audit(novel_dir, chapter)
        if report is None:
            actual[chapter] = "missing"
            continue
        actual[chapter] = "pass" if report.get("status") == "pass" else "fail"

    for entry in entries:
        number = entry_number(entry)
        if not isinstance(number, int):
            continue
        truth = actual.get(number, "missing")
        claim = str(entry.get("audit", "")).strip()
        claim_is_pass = claim.lower() in {"pass", "passed"} or (
            "通过" in claim and "未通过" not in claim and "未审计" not in claim
        )
        if claim_is_pass and truth != "pass":
            changes.append(
                {
                    "chapter": number,
                    "claimed": claim,
                    "actual": STATUS_LABELS[truth],
                    "reason": "声称通过但无对应审计报告" if truth == "missing" else "实际未通过",
                }
            )
        entry["audit_status"] = truth
        entry["audit"] = STATUS_LABELS[truth]
        entry["audit_verified_at"] = datetime.now().isoformat(timespec="seconds")

    total = len(on_disk)
    audited = sum(1 for chapter in on_disk if actual.get(chapter) in {"pass", "fail"})
    passed = sum(1 for chapter in on_disk if actual.get(chapter) == "pass")
    state["audit_coverage"] = {
        "total_chapters": total,
        "audited": audited,
        "passed": passed,
        "rate": round(audited / total, 4) if total else 0.0,
        "reconciled_at": datetime.now().isoformat(timespec="seconds"),
    }
    state["last_updated"] = state["audit_coverage"]["reconciled_at"]

    backup = ""
    if apply:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = novel_dir / "素材" / "state_backups" / f"novel_state.json.bak-{stamp}"
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(state_path, backup_path)
        backup = rel(backup_path, PROJECT_ROOT)
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "novel_dir": rel(novel_dir, PROJECT_ROOT),
        "chapters_on_disk": total,
        "audited": audited,
        "passed": passed,
        "rate": state["audit_coverage"]["rate"],
        "false_claims": len(changes),
        "changes": changes[:50],
        "applied": apply,
        "backup": backup,
    }


def discover_all() -> list[Path]:
    dirs: list[Path] = []
    for state_path in sorted((PROJECT_ROOT / "novel_output").glob("*/*/novel_state.json")):
        dirs.append(state_path.parent)
    return dirs


def main() -> int:
    parser = argparse.ArgumentParser(description="对账 novel_state 审计状态与真实审计报告")
    parser.add_argument("--novel-dir", default="", help="单个小说目录")
    parser.add_argument("--all", action="store_true", help="扫描 novel_output 下全部项目")
    parser.add_argument("--apply", action="store_true", help="实际写回（默认 dry-run）")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    targets: list[Path] = []
    if args.novel_dir:
        targets = [Path(args.novel_dir) if Path(args.novel_dir).is_absolute() else PROJECT_ROOT / args.novel_dir]
    elif args.all:
        targets = discover_all()
    else:
        parser.error("需要 --novel-dir 或 --all")

    results = [reconcile(path, apply=args.apply) for path in targets]

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0

    print(f"{'项目':<45}{'章节':>6}{'已审计':>8}{'通过':>6}{'虚假声称':>8}")
    print("-" * 75)
    for item in results:
        if "error" in item:
            print(f"{item['novel_dir']:<45}  {item['error']}")
            continue
        print(
            f"{item['novel_dir']:<45}{item['chapters_on_disk']:>6}"
            f"{item['audited']:>8}{item['passed']:>6}{item['false_claims']:>8}"
        )
        for change in item["changes"][:5]:
            print(
                f"    ch{change['chapter']:03d}: 声称'{change['claimed']}' → 实际'{change['actual']}'"
                f"（{change['reason']}）"
            )
    if not args.apply:
        print("\n[dry-run] 未写回。加 --apply 生效（会自动备份 novel_state.json）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
