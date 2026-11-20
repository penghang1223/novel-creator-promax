#!/usr/bin/env python3
"""Create, validate, inspect and render structured chapter review results.

The reviewer agent returns JSON only. This CLI is the deterministic side of
the contract: it binds the review to the exact chapter revision, validates
source quotes, computes the blocking gate and renders the human report.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from novel_creation_promax.core.review_basis import (  # noqa: E402
    build_review_basis,
    expected_versions_from_basis,
)
from novel_creation_promax.core.revision_control import ensure_current_revision  # noqa: E402
from novel_creation_promax.core.review_result import (  # noqa: E402
    DuplicateJsonKeyError,
    chapter_target,
    init_review_result,
    load_review_result_checked,
    parse_review_json,
    render_review_markdown,
    review_gate,
    review_path,
    save_review_result,
    validate_review_result,
)


def resolve(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else Path.cwd() / path


def cmd_init(args: argparse.Namespace) -> int:
    novel_dir = resolve(args.novel_dir)
    path = resolve(args.output) if args.output else review_path(novel_dir, args.chapter)
    if path.exists() and not args.force:
        print(f"[ERROR] 审稿文件已存在: {path}（使用 --force 覆盖）", file=sys.stderr)
        return 1
    target = chapter_target(novel_dir, args.chapter)
    if target is None:
        print(
            f"[WARN] 第{args.chapter}章正文不存在，模板未绑定审稿目标；"
            "起草后再运行 `target --ensure-revision` 或 `save --bind-target`。",
            file=sys.stderr,
        )
    else:
        ensure_current_revision(novel_dir, args.chapter, source="review_target")
        target = chapter_target(novel_dir, args.chapter)
    bundle = build_review_basis(novel_dir, args.chapter) if target is not None else None
    payload = init_review_result(
        args.chapter,
        mode=args.mode,
        target=target,
        basis=bundle["basis"] if bundle else None,
        expected_versions=bundle["expected_versions"] if bundle else None,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[OK] 已创建待填写审稿模板: {path}")
    return 0


def load_target(args: argparse.Namespace) -> tuple[dict | None, list[str]]:
    if getattr(args, "input", ""):
        path = resolve(args.input)
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            return None, [f"读取审稿 JSON 失败: {exc}"]
        try:
            return parse_review_json(raw), []
        except (DuplicateJsonKeyError, ValueError) as exc:
            return None, [str(exc)]
    return load_review_result_checked(resolve(args.novel_dir), args.chapter)


def cmd_target(args: argparse.Namespace) -> int:
    novel_dir = resolve(args.novel_dir)
    target = chapter_target(novel_dir, args.chapter)
    if target is None:
        print(f"[ERROR] 第{args.chapter}章正文不存在", file=sys.stderr)
        return 1
    if args.ensure_revision:
        ensure_current_revision(novel_dir, args.chapter, source="review_target")
        target = chapter_target(novel_dir, args.chapter)
    output = target
    if args.with_basis:
        output = {"target": target, **build_review_basis(novel_dir, args.chapter)}
    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(f"file={target['chapter_file']}")
        print(f"sha256={target['sha256']}")
        print(f"word_count={target['word_count']}")
        print(f"revision_id={target.get('revision_id') or ''}")
        print(f"revision_version={target.get('revision_version') or ''}")
        print(f"revision_state={target.get('revision_state', '')}")
        if args.with_basis:
            basis = output["basis"]
            print(f"basis_fingerprint={basis['input_fingerprint']}")
            print(f"expected_versions={len(output['expected_versions'])}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    payload, load_errors = load_target(args)
    if load_errors:
        print("[ERROR] 审稿 JSON 无法读取：", file=sys.stderr)
        for error in load_errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    if payload is None:
        print("[ERROR] 未找到审稿结果", file=sys.stderr)
        return 1
    report = validate_review_result(payload, chapter=args.chapter)
    if report["status"] == "pass":
        gate = review_gate(resolve(args.novel_dir), args.chapter)
        if gate["status"] in {"stale", "invalid"}:
            report["status"] = "fail"
            existing = set(report["errors"])
            for error in gate["report"]["errors"]:
                if error not in existing:
                    report["errors"].append(error)
        elif gate["status"] == "blocked":
            report["warnings"].append("契约有效，但存在 blocker，commit 会被阻断")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"[{report['status'].upper()}] review result 契约校验")
        for error in report["errors"]:
            print(f"  [ERROR] {error}")
        for warning in report["warnings"]:
            print(f"  [WARN] {warning}")
    return 0 if report["status"] == "pass" else 1


def cmd_save(args: argparse.Namespace) -> int:
    path = resolve(args.input)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"[ERROR] 无法读取审稿 JSON: {exc}", file=sys.stderr)
        return 1
    try:
        payload = parse_review_json(raw)
    except (DuplicateJsonKeyError, ValueError) as exc:
        print(f"[ERROR] 审稿 JSON 无效: {exc}", file=sys.stderr)
        return 1
    novel_dir = resolve(args.novel_dir)
    if args.bind_target:
        target = chapter_target(novel_dir, args.chapter)
        if target is None:
            print(f"[ERROR] 第{args.chapter}章正文不存在，无法绑定审稿目标", file=sys.stderr)
            return 1
        ensure_current_revision(novel_dir, args.chapter, source="review_target")
        target = chapter_target(novel_dir, args.chapter)
        payload = {**payload, "target": target}
        if not payload.get("basis"):
            bundle = build_review_basis(novel_dir, args.chapter)
            payload["basis"] = bundle["basis"]
            payload["expected_versions"] = bundle["expected_versions"]
    if payload.get("basis") and not payload.get("expected_versions"):
        payload["expected_versions"] = expected_versions_from_basis(payload["basis"])
    report = validate_review_result(payload, chapter=args.chapter)
    if report["status"] != "pass":
        print("[ERROR] 审稿 JSON 契约校验失败，拒绝写入：", file=sys.stderr)
        for error in report["errors"]:
            print(f"  - {error}", file=sys.stderr)
        return 1
    try:
        path = save_review_result(novel_dir, args.chapter, payload)
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    print(f"[OK] 审稿结果已写入: {path}")
    if args.bind_target:
        print("[INFO] 已按当前正文绑定 target.sha256；正文再次修改后该审稿会变为 stale。")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    gate = review_gate(resolve(args.novel_dir), args.chapter)
    payload = {
        "status": gate["status"],
        "blocking_count": gate["blocking_count"],
        "path": str(gate["path"]),
        "target": gate.get("target", {}),
        "issues": gate["issues"],
        "report": gate["report"],
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"status={gate['status']} blocking={gate['blocking_count']} path={gate['path']}")
        target = gate.get("target") or {}
        if target.get("sha256"):
            print(
                f"target={target.get('chapter_file', '')} sha256={target['sha256'][:16]}… "
                f"revision={target.get('revision_id') or '未绑定'}"
            )
        basis = gate.get("basis") or {}
        if basis.get("input_fingerprint"):
            print(f"basis_fingerprint={basis['input_fingerprint'][:16]}…")
        for issue in gate["issues"]:
            if issue["severity"] == "blocker":
                print(f"  [BLOCKER] {issue['id']} {issue['dimension']}: {issue['evidence']}")
        for error in gate["report"]["errors"]:
            print(f"  [ERROR] {error}")
    if gate["status"] in {"blocked", "invalid", "stale"}:
        return 1
    if gate["status"] == "missing" and args.require:
        return 1
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    payload, load_errors = load_target(args)
    if load_errors:
        print("[ERROR] 审稿 JSON 无法读取：", file=sys.stderr)
        for error in load_errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    if payload is None:
        print("[ERROR] 未找到审稿结果", file=sys.stderr)
        return 1
    markdown = render_review_markdown(payload, chapter=args.chapter)
    if args.output:
        output = resolve(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(markdown, encoding="utf-8")
        print(f"[OK] 审稿 Markdown 已生成: {output}")
    else:
        print(markdown, end="")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="章节审稿结果契约工具")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--novel-dir", required=True, help="小说项目目录")
        p.add_argument("--chapter", type=int, required=True, help="章节号")

    init = sub.add_parser("init", help="创建待填写的审稿模板")
    add_common(init)
    init.add_argument("--mode", choices=["single", "batch"], default="single")
    init.add_argument("--output", default="", help="自定义输出路径")
    init.add_argument("--force", action="store_true", help="覆盖已有文件")
    init.set_defaults(func=cmd_init)

    target = sub.add_parser("target", help="打印当前正文的审稿目标（文件/哈希/字数/revision）")
    add_common(target)
    target.add_argument("--json", action="store_true")
    target.add_argument(
        "--with-basis",
        action="store_true",
        help="同时输出 basis 与 expected_versions（审稿必须回传）",
    )
    target.add_argument(
        "--ensure-revision",
        action="store_true",
        help="正文变化时创建新的 revision 记录，并把审稿绑定到该 revision",
    )
    target.set_defaults(func=cmd_target)

    validate = sub.add_parser("validate", help="校验审稿 JSON 契约、目标哈希与原文引用")
    add_common(validate)
    validate.add_argument("--input", default="", help="自定义输入路径")
    validate.add_argument("--json", action="store_true")
    validate.set_defaults(func=cmd_validate)

    save = sub.add_parser("save", help="校验并写入审稿 JSON")
    add_common(save)
    save.add_argument("--input", required=True, help="reviewer 返回的 JSON 文件")
    save.add_argument(
        "--bind-target",
        action="store_true",
        help="用当前正文的 SHA-256 覆盖 target；仅用于 reviewer 未自行计算哈希时",
    )
    save.set_defaults(func=cmd_save)

    status = sub.add_parser("status", help="查看审稿门禁状态")
    add_common(status)
    status.add_argument("--json", action="store_true")
    status.add_argument("--require", action="store_true", help="缺失审稿结果也视为失败")
    status.set_defaults(func=cmd_status)

    render = sub.add_parser("render", help="把审稿 JSON 渲染为 Markdown")
    add_common(render)
    render.add_argument("--input", default="", help="自定义输入路径")
    render.add_argument("--output", default="", help="Markdown 输出路径；不填则打印到 stdout")
    render.set_defaults(func=cmd_render)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
