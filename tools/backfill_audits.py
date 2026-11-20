#!/usr/bin/env python3
"""
backfill_audits.py — 批量为已写章节补跑 post_write_audit。

适用于历史章节：novel_output/番茄/002_我发疯后… 已经写到第43章，但只跑过 ch22-32 的审计。
用本脚本一次性补完。

关键点：
  - 直接调用 post_write_audit.py，不走 write_pipeline.post，避免触发不需要的 style/character 检查
  - 自动跳过已存在 audit_chNNN.json 的章节（除非 --force）
  - 同时更新 novel_state.json.chapters[NNN].audit_status

用法:
  python tools/backfill_audits.py --novel-dir "novel_output/番茄/002_我发疯后全世界都正常了"
  python tools/backfill_audits.py --novel-dir "..." --from-chapter 1 --to-chapter 21
  python tools/backfill_audits.py --novel-dir "..." --force      # 已有也重跑
  python tools/backfill_audits.py --novel-dir "..." --dry-run    # 只打印计划，不执行
  python tools/backfill_audits.py --all --dry-run                 # 全库只打印计划
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "novel_creation_promax" / "scripts"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from novel_creation_promax.core.jsonio import load_json, now_iso, save_json  # noqa: E402
from novel_creation_promax.core.paths import list_chapter_files  # noqa: E402
from novel_creation_promax.core.project_state import ensure_state_shape  # noqa: E402
from post_write_audit import audit_chapter, build_audit_payload, sync_novel_state  # noqa: E402

def list_chapters(novel_dir: Path) -> list[tuple[int, Path]]:
    return list_chapter_files(novel_dir)


def find_chapter(items: list[tuple[int, Path]], n: int) -> Path | None:
    for ch, p in items:
        if ch == n:
            return p
    return None


def update_state(novel_dir: Path, chapter: int, audit_report: str, status: str) -> None:
    state_path = novel_dir / "novel_state.json"
    state = ensure_state_shape(
        load_json(state_path, {}),
        title=novel_dir.name,
        platform=novel_dir.parent.name,
    )
    key = f"{chapter:03d}"
    ch = state["chapters"].setdefault(key, {})
    ch["audit_report"] = audit_report
    ch["audit_status"] = status
    ch["updated_at"] = now_iso()
    state["audit_history"] = [
        item
        for item in state["audit_history"]
        if not (
            isinstance(item, dict)
            and item.get("chapter") == chapter
            and item.get("source") == "backfill"
        )
    ]
    state["audit_history"].append({
        "chapter": chapter,
        "report": audit_report,
        "status": status,
        "updated_at": now_iso(),
        "source": "backfill",
    })
    state["updated_at"] = now_iso()
    save_json(state_path, state)


def run_audit(novel_dir: Path, chapter: int, chapter_file: Path, prev_file: Path | None) -> tuple[int, Path]:
    audit_report = novel_dir / "素材" / f"audit_ch{chapter:03d}.json"
    audit_report.parent.mkdir(parents=True, exist_ok=True)
    text = chapter_file.read_text(encoding="utf-8")
    previous = prev_file.read_text(encoding="utf-8") if prev_file else None
    results = audit_chapter(text, chapter_file.stem, previous)
    payload = build_audit_payload(results)
    audit_report.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    state_path = novel_dir / "novel_state.json"
    if state_path.exists():
        sync_novel_state(str(state_path), str(audit_report), payload)
    return (0 if results.get("pass") else 1), audit_report


def main() -> int:
    ap = argparse.ArgumentParser()
    scope = ap.add_mutually_exclusive_group(required=True)
    scope.add_argument("--novel-dir")
    scope.add_argument("--all", action="store_true", help="扫描 novel_output 下所有有章节的项目")
    ap.add_argument("--from-chapter", type=int, default=1)
    ap.add_argument("--to-chapter", type=int, default=None)
    ap.add_argument("--force", action="store_true", help="已有 audit 也重跑")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.novel_dir:
        novel_dir = Path(args.novel_dir)
        if not novel_dir.is_absolute():
            novel_dir = PROJECT_ROOT / novel_dir
        targets_dirs = [novel_dir]
    else:
        targets_dirs = sorted(
            path.parent
            for path in (PROJECT_ROOT / "novel_output").glob("*/*/正文")
            if path.is_dir()
        )

    total_failed = 0
    for novel_dir in targets_dirs:
        if not novel_dir.exists():
            print(f"[FATAL] 目录不存在: {novel_dir}", file=sys.stderr)
            total_failed += 1
            continue
        chapters = list_chapters(novel_dir)
        if not chapters:
            print(f"[skip] 没找到章节文件: {novel_dir}")
            continue

        max_ch = chapters[-1][0]
        to_ch = args.to_chapter or max_ch
        targets = [(n, p) for n, p in chapters if args.from_chapter <= n <= to_ch]
        print(f"目标章节: {args.from_chapter}-{to_ch}，共 {len(targets)} 章。")
        print(f"小说目录: {novel_dir.relative_to(PROJECT_ROOT)}")

        skipped, ran, passed, failed = 0, 0, 0, 0
        for n, p in targets:
            audit_report = novel_dir / "素材" / f"audit_ch{n:03d}.json"
            if audit_report.exists() and not args.force:
                print(f"  [skip] 第{n}章 已有 audit → {audit_report.name}")
                skipped += 1
                continue
            prev = find_chapter(chapters, n - 1)
            print(f"  [run ] 第{n}章 {p.name}")
            if args.dry_run:
                ran += 1
                continue
            had_state = (novel_dir / "novel_state.json").exists()
            try:
                rc, report_path = run_audit(novel_dir, n, p, prev)
            except Exception as exc:  # noqa: BLE001
                print(f"  [error] 第{n}章审计失败: {exc}", file=sys.stderr)
                failed += 1
                continue
            status = "pass" if rc == 0 else "fail"
            if had_state:
                update_state(novel_dir, n, str(report_path.relative_to(novel_dir)), status)
            ran += 1
            if rc == 0:
                passed += 1
            else:
                failed += 1

        print(f"\n汇总：跳过 {skipped}，执行 {ran}，通过 {passed}，失败 {failed}")
        total_failed += failed
    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
