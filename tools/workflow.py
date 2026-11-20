#!/usr/bin/env python3
"""Verifiable project workflow: research -> idea -> init -> write -> publish.

State lives in the user workspace at ``novel_output/_workspace/workflow.json``.
The tool is read-mostly: ``gate`` never mutates; ``advance`` only records a
transition after its evidence checks pass.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from novel_creation_promax.core.jsonio import load_json, now_iso, save_json  # noqa: E402
from novel_creation_promax.core.paths import rel  # noqa: E402
from novel_creation_promax.core.roots import workspace_root  # noqa: E402

STAGES = ("research", "idea", "init", "write", "publish")
LABELS = {
    "research": "平台调研",
    "idea": "创意生成",
    "init": "立项封存",
    "write": "正文写作",
    "publish": "发布",
}
SCHEMA_VERSION = "1.0"


def workflow_path(workspace: Path) -> Path:
    return workspace / "novel_output" / "_workspace" / "workflow.json"


def _empty_state(workspace: Path) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "stage": "",
        "status": "not_started",
        "platform": "",
        "genre": "",
        "research_report": "",
        "idea_card": "",
        "novel_dir": "",
        "history": [],
        "overrides": [],
        "created_at": "",
        "updated_at": "",
    }


def load_state(workspace: Path) -> dict[str, Any]:
    payload = load_json(workflow_path(workspace), {})
    state = _empty_state(workspace)
    if isinstance(payload, dict):
        state.update(payload)
    for key in ("history", "overrides"):
        if not isinstance(state.get(key), list):
            state[key] = []
    return state


def _save_state(workspace: Path, state: dict[str, Any]) -> None:
    state["schema_version"] = SCHEMA_VERSION
    state["updated_at"] = now_iso()
    save_json(workflow_path(workspace), state)


def _resolve(workspace: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (workspace / path)


def _stored_path(workspace: Path, path: Path) -> str:
    return rel(path.resolve(), workspace.resolve())


def _next_stage(stage: str) -> str:
    if stage not in STAGES:
        return STAGES[0]
    index = STAGES.index(stage)
    return STAGES[index + 1] if index + 1 < len(STAGES) else ""


def _latest(workspace: Path, patterns: tuple[str, ...], platform: str = "") -> Path | None:
    for pattern in patterns:
        candidates = [path for path in sorted(workspace.glob(pattern)) if path.is_file()]
        if platform:
            matched = [path for path in candidates if platform in path.name]
            candidates = matched or candidates
        if candidates:
            return candidates[-1]
    return None


def _novel_state(workspace: Path, state: dict[str, Any], novel_dir_arg: str = "") -> tuple[Path | None, dict[str, Any]]:
    raw = novel_dir_arg or str(state.get("novel_dir") or "")
    if not raw:
        return None, {}
    novel_dir = _resolve(workspace, raw).resolve()
    payload = load_json(novel_dir / "novel_state.json", {})
    return novel_dir, payload if isinstance(payload, dict) else {}


def _accepted_commit(novel_dir: Path) -> bool:
    commit_dir = novel_dir / "素材" / "commits"
    if not commit_dir.is_dir():
        return False
    for path in sorted(commit_dir.glob("chapter_*.commit.json")):
        payload = load_json(path, {})
        if isinstance(payload, dict) and payload.get("status") == "accepted":
            return True
    return False


def _published(novel_state: dict[str, Any]) -> bool:
    publish = novel_state.get("publish_state", {})
    if isinstance(publish, dict):
        for item in publish.values():
            if not isinstance(item, dict):
                continue
            status = str(item.get("status", "")).strip().lower()
            if status and status not in {"not_synced", "pending", "none"}:
                return True
    return False


def check_target(
    workspace: Path,
    state: dict[str, Any],
    target: str,
    *,
    evidence: str = "",
    novel_dir_arg: str = "",
) -> list[str]:
    missing: list[str] = []
    if target not in STAGES:
        return [f"未知阶段: {target}"]

    if target == "research":
        explicit = evidence or str(state.get("research_report") or "")
        path = _resolve(workspace, explicit) if explicit else _latest(
            workspace,
            ("素材/调研/*.md",),
            platform=str(state.get("platform") or ""),
        )
        if path is None or not path.is_file() or path.stat().st_size == 0:
            missing.append("缺少有效的调研报告（素材/调研/）：先完成 /research")
        return missing

    if target == "idea":
        explicit = evidence or str(state.get("idea_card") or "")
        path = _resolve(workspace, explicit) if explicit else _latest(
            workspace, ("创意/创意卡_*.md", "创意/*.md")
        )
        if path is None or not path.is_file() or path.stat().st_size == 0:
            missing.append("缺少有效的创意卡（创意/）：先完成 /idea")
        return missing

    novel_dir, novel_state = _novel_state(workspace, state, novel_dir_arg)
    if target == "init":
        idea_path = _latest(workspace, ("创意/创意卡_*.md", "创意/*.md"))
        if not str(state.get("idea_card") or "").strip() and idea_path is None:
            missing.append("缺少创意卡（创意/）：先完成 /idea")
        if novel_dir is None or not novel_dir.is_dir():
            missing.append("缺少 novel_dir")
        elif not (novel_dir / "novel_state.json").is_file():
            missing.append(f"novel_state.json 不存在: {rel(novel_dir / 'novel_state.json', workspace)}")
        else:
            gate = novel_state.get("workflow_gate", {})
            if not isinstance(gate, dict) or gate.get("can_write_chapter") is not True:
                missing.append("立项门禁未通过：先运行 project_bootstrap_pipeline.py seal")
    elif target == "write":
        if novel_dir is None or not novel_dir.is_dir():
            missing.append("缺少 novel_dir")
        elif not _accepted_commit(novel_dir):
            missing.append("没有 accepted 的 chapter commit：先写完并通过 post")
    elif target == "publish":
        if novel_dir is None or not novel_dir.is_dir():
            missing.append("缺少 novel_dir")
        elif not _published(novel_state):
            missing.append("novel_state.publish_state 没有已同步/已发布记录")
    return missing


def _render_status(state: dict[str, Any], missing: list[str]) -> str:
    stage = state.get("stage") or ""
    next_stage = _next_stage(stage) if stage else "research"
    lines = [
        "工作流: " + " → ".join(f"{STAGES[i]}({LABELS[STAGES[i]]})" for i in range(len(STAGES))),
        f"当前: {stage or '未开始'} {('(' + LABELS[stage] + ')') if stage else ''}".rstrip(),
        f"下一步: {next_stage or '已完成'}",
        f"平台/题材: {state.get('platform') or '-'} / {state.get('genre') or '-'}",
        f"调研: {state.get('research_report') or '-'}",
        f"创意: {state.get('idea_card') or '-'}",
        f"项目: {state.get('novel_dir') or '-'}",
    ]
    if next_stage:
        lines.append("下一步门禁: " + ("通过" if not missing else "未通过"))
        for item in missing:
            lines.append(f"  - {item}")
    if state.get("overrides"):
        lines.append(f"强制跳阶段记录: {len(state['overrides'])} 条")
    return "\n".join(lines)


def _cmd_start(workspace: Path, args: argparse.Namespace) -> int:
    state = load_state(workspace)
    if state.get("created_at"):
        next_stage = _next_stage(state.get("stage", "")) or "publish"
        print(_render_status(state, check_target(workspace, state, next_stage)))
        return 0
    state.update(
        {
            "stage": "",
            "status": "in_progress",
            "platform": args.platform,
            "genre": args.genre,
            "created_at": now_iso(),
        }
    )
    state["history"].append(
        {"stage": "", "status": "in_progress", "at": now_iso(), "note": "工作流启动"}
    )
    _save_state(workspace, state)
    print("工作流已启动: 等待 research 阶段证据")
    print(f"下一步: 运行 /novel-creator-pro:research {args.platform} {args.genre}")
    return 0


def _cmd_status(workspace: Path, args: argparse.Namespace) -> int:
    state = load_state(workspace)
    next_stage = _next_stage(state.get("stage", "")) if state.get("stage") else "research"
    missing = check_target(workspace, state, next_stage) if next_stage else []
    if args.json:
        payload = dict(state)
        payload["next"] = next_stage
        payload["next_gate"] = "pass" if not missing else "fail"
        payload["missing"] = missing
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(_render_status(state, missing))
    return 0


def _cmd_gate(workspace: Path, args: argparse.Namespace) -> int:
    state = load_state(workspace)
    if not state.get("created_at"):
        print("error: 工作流尚未开始，先运行 start", file=sys.stderr)
        return 2
    missing = check_target(workspace, state, args.to, evidence=args.evidence, novel_dir_arg=args.novel_dir)
    if missing:
        print(f"门禁未通过: {args.to}", file=sys.stderr)
        for item in missing:
            print(f"  - {item}", file=sys.stderr)
        return 1
    print(f"门禁通过: {args.to}")
    return 0


def _cmd_advance(workspace: Path, args: argparse.Namespace) -> int:
    state = load_state(workspace)
    if not state.get("created_at"):
        print("error: 工作流尚未开始，先运行 start", file=sys.stderr)
        return 2
    target = args.to
    if target not in STAGES:
        print(f"error: 未知阶段: {target}", file=sys.stderr)
        return 2

    current = state["stage"]
    current_index = STAGES.index(current) if current in STAGES else -1
    target_index = STAGES.index(target)
    if not args.force and target_index > current_index + 1:
        print(f"error: 不能跳阶段：当前 {current}，目标 {target}。确需跳过请加 --force --reason", file=sys.stderr)
        return 1

    missing = [] if args.force else check_target(
        workspace, state, target, evidence=args.evidence, novel_dir_arg=args.novel_dir
    )
    if missing:
        print(f"门禁未通过: {target}", file=sys.stderr)
        for item in missing:
            print(f"  - {item}", file=sys.stderr)
        return 1

    if target == "research":
        explicit = args.evidence
        path = _resolve(workspace, explicit) if explicit else _latest(
            workspace, ("素材/调研/*.md",), platform=str(state.get("platform") or "")
        )
        if path:
            state["research_report"] = _stored_path(workspace, path)
    elif target == "idea":
        explicit = args.evidence
        path = _resolve(workspace, explicit) if explicit else _latest(workspace, ("创意/创意卡_*.md", "创意/*.md"))
        if path:
            state["idea_card"] = _stored_path(workspace, path)
    if args.novel_dir:
        state["novel_dir"] = _stored_path(workspace, _resolve(workspace, args.novel_dir))

    state["stage"] = target
    state["status"] = "done"
    state["history"].append(
        {
            "stage": target,
            "status": "forced" if args.force else "done",
            "at": now_iso(),
            "note": args.note,
        }
    )
    if args.force:
        state["overrides"].append(
            {"target": target, "reason": args.reason.strip(), "at": now_iso()}
        )
    _save_state(workspace, state)
    print(f"已推进到: {target}（{LABELS[target]}）")
    next_stage = _next_stage(target)
    if next_stage:
        print(f"下一步: {next_stage}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="小说项目工作流阶段门禁")
    parser.add_argument("--workspace", default="", help="工作区根目录，默认读取 CLAUDE_PROJECT_DIR")
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start", help="启动工作流")
    start.add_argument("--platform", required=True)
    start.add_argument("--genre", default="")

    status = sub.add_parser("status", help="查看当前阶段与下一步")
    status.add_argument("--json", action="store_true")

    gate = sub.add_parser("gate", help="只校验门禁，不改变状态")
    gate.add_argument("--to", required=True, choices=STAGES)
    gate.add_argument("--evidence", default="")
    gate.add_argument("--novel-dir", default="")

    advance = sub.add_parser("advance", help="推进到下一阶段")
    advance.add_argument("--to", required=True, choices=STAGES)
    advance.add_argument("--evidence", default="")
    advance.add_argument("--novel-dir", default="")
    advance.add_argument("--note", default="")
    advance.add_argument("--force", action="store_true")
    advance.add_argument("--reason", default="")

    args = parser.parse_args()
    workspace = Path(args.workspace).expanduser().resolve() if args.workspace else workspace_root()

    if args.command == "start":
        return _cmd_start(workspace, args)
    if args.command == "status":
        return _cmd_status(workspace, args)
    if args.command == "gate":
        return _cmd_gate(workspace, args)
    if args.command == "advance":
        if args.force and not args.reason.strip():
            print("error: --force 必须同时提供 --reason", file=sys.stderr)
            return 2
        return _cmd_advance(workspace, args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
