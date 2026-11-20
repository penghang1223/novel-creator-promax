#!/usr/bin/env python3
"""Inspect and refresh the derived author-truth / reader-known views.

The source of truth is always ``设定/真相文件/``. This tool only builds or
prints the derived layers used by the writing pipeline; it never edits truth
files.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "novel_creation_promax" / "scripts"
for entry in (PROJECT_ROOT, SCRIPTS_DIR):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from novel_creation_promax.core.jsonio import load_json, save_json  # noqa: E402
from story_truth_manager import compile_rule_stack, write_power_ladder_view, write_truth_views  # noqa: E402


def resolve(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else Path.cwd() / path


def rule_stack_path(novel_dir: Path, chapter: int) -> Path:
    return novel_dir / "摘要" / f"chapter_{chapter:03d}_rule_stack.json"


def load_or_compile(novel_dir: Path, chapter: int, *, write: bool = False) -> dict:
    path = rule_stack_path(novel_dir, chapter)
    payload = load_json(path, {})
    if isinstance(payload, dict) and isinstance(payload.get("truth_layers"), dict):
        return payload
    payload = compile_rule_stack(novel_dir, chapter, f"第{chapter}章")
    if write:
        save_json(path, payload)
    return payload


def layer_entries(stack: dict, layer: str) -> list[dict]:
    layers = stack.get("truth_layers") or {}
    if layer == "author":
        return layers.get("author_truth") or []
    if layer == "reader":
        return layers.get("reader_known") or []
    if layer == "unrevealed":
        return layers.get("unrevealed_facts") or []
    raise ValueError(f"未知 layer: {layer}")


def format_entries(entries: list[dict]) -> str:
    lines: list[str] = []
    if not entries:
        return "（无）"
    for item in entries:
        marker = "读者已知" if item.get("reader_known") else "未揭示"
        lines.append(
            f"[{marker}] {item.get('type')}:{item.get('id')} {item.get('summary')}"
        )
        if item.get("reveal_status"):
            lines.append(f"  状态: {item['reveal_status']}")
        if item.get("reveal_chapter") is not None:
            lines.append(f"  章节: {item['reveal_chapter']}")
    return "\n".join(lines)


def cmd_sync(args: argparse.Namespace) -> int:
    novel_dir = resolve(args.novel_dir)
    stack = load_or_compile(novel_dir, args.chapter, write=True)
    views = write_truth_views(stack, novel_dir) + [write_power_ladder_view(stack, novel_dir)]
    stats = stack.get("truth_layers", {}).get("stats", {})
    print(
        f"[OK] author={stats.get('author_truth', 0)} "
        f"reader={stats.get('reader_known', 0)} "
        f"unrevealed={stats.get('unrevealed', 0)} "
        f"characters={stats.get('characters', 0)}"
    )
    for view in views:
        print(f"[OK] {view}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    novel_dir = resolve(args.novel_dir)
    stack = load_or_compile(novel_dir, args.chapter)
    entries = layer_entries(stack, args.layer)
    if args.json:
        print(json.dumps(entries, ensure_ascii=False, indent=2))
    else:
        print(format_entries(entries))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    novel_dir = resolve(args.novel_dir)
    stack = load_or_compile(novel_dir, args.chapter)
    layers = stack.get("truth_layers")
    if not isinstance(layers, dict):
        print("[FAIL] rule_stack 缺少 truth_layers", file=sys.stderr)
        return 1
    author = layers.get("author_truth") or []
    reader = layers.get("reader_known") or []
    unrevealed = layers.get("unrevealed_facts") or []
    errors: list[str] = []
    if len(author) != len(reader) + len(unrevealed):
        errors.append(
            f"author_truth 数量 {len(author)} != reader_known {len(reader)} + unrevealed {len(unrevealed)}"
        )
    seen: set[tuple[str, str]] = set()
    for item in author:
        key = (str(item.get("type") or ""), str(item.get("id") or ""))
        if not key[1]:
            errors.append("存在缺少 id 的真相条目")
        if key in seen:
            errors.append(f"重复条目: {key}")
        seen.add(key)
    if errors:
        print("[FAIL] " + "; ".join(errors), file=sys.stderr)
        return 1
    print(
        f"[OK] truth layers valid: author={len(author)} reader={len(reader)} "
        f"unrevealed={len(unrevealed)} characters={len(layers.get('character_knowledge') or {})}"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="作者真相 / 读者已知 分层工具")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--novel-dir", required=True, help="小说项目目录")
        p.add_argument("--chapter", type=int, required=True, help="章节号")

    sync = sub.add_parser("sync", help="生成/刷新 追踪/时间线/作者真相.md 和 读者已知.md")
    add_common(sync)
    sync.set_defaults(func=cmd_sync)

    show = sub.add_parser("show", help="查看某一层的条目")
    add_common(show)
    show.add_argument("--layer", choices=["author", "reader", "unrevealed"], default="reader")
    show.add_argument("--json", action="store_true")
    show.set_defaults(func=cmd_show)

    validate = sub.add_parser("validate", help="校验分层完整性")
    add_common(validate)
    validate.set_defaults(func=cmd_validate)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
