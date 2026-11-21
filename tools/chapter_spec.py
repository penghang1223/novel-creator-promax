#!/usr/bin/env python3
"""章节 / 场景 spec 工具。

- scaffold: 生成章节 spec 模板
- validate: 校验标题、场景节点、张力曲线和 change
- to-scene-plan: 转成 scene_passport.py 可用的场景计划
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

CHANGES = {"信息", "关系", "计划", "风险", "权力", "理解", "情绪"}
SCENE_TYPES = {"主要", "次要", "内心", "讲述"}
SCALES = {"压缩", "扩展"}


def empty_spec(chapter: int, title: str = "") -> dict[str, Any]:
    return {
        "chapter": chapter,
        "title": title or f"第{chapter}章",
        "summary": "",
        "before_state": {"characters": [], "plot_hooks": []},
        "after_state": {"characters": [], "plot_advances": []},
        "must_happen": [],
        "scenes": [
            {
                "type": "主要",
                "goal": "",
                "result": "",
                "outside": ["行动：", "阻碍：", "助力：", "转向："],
                "inside": ["反应：", "消化：", "选择：", "决定："],
                "narration": "",
                "scale": "扩展",
            }
        ],
        "tension_curve": [
            {"position": 0, "value": 3, "note": "铺垫"},
            {"position": 50, "value": 8, "note": "高潮"},
            {"position": 100, "value": 5, "note": "余波"},
        ],
        "change": "信息",
        "new_hooks": [],
    }


def _non_empty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_spec(spec: Any) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(spec, dict):
        return {"status": "fail", "errors": ["spec 顶层必须是 object"], "warnings": []}

    chapter = spec.get("chapter")
    if not isinstance(chapter, int) or chapter < 1:
        errors.append("chapter 必须是正整数")
    if not _non_empty(spec.get("title")):
        errors.append("title 不能为空")
    if not _non_empty(spec.get("summary")):
        errors.append("summary 不能为空")

    for key in ("before_state", "after_state"):
        state = spec.get(key)
        if not isinstance(state, dict):
            errors.append(f"{key} 必须是 object")
        elif not isinstance(state.get("characters"), list):
            errors.append(f"{key}.characters 必须是数组")

    if not isinstance(spec.get("must_happen"), list):
        errors.append("must_happen 必须是数组")

    scenes = spec.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        errors.append("scenes 必须是非空数组")
        scenes = []
    for index, scene in enumerate(scenes, 1):
        prefix = f"scenes[{index}]"
        if not isinstance(scene, dict):
            errors.append(f"{prefix} 必须是 object")
            continue
        if scene.get("type") not in SCENE_TYPES:
            errors.append(f"{prefix}.type 必须是 {'/'.join(sorted(SCENE_TYPES))}")
        goal = scene.get("goal")
        result = scene.get("result")
        if not _non_empty(goal):
            errors.append(f"{prefix}.goal 不能为空")
        if not _non_empty(result):
            errors.append(f"{prefix}.result 不能为空")
        if _non_empty(goal) and goal.strip() == str(result or "").strip():
            errors.append(f"{prefix}.result 不能等于 goal（每场戏必须留下差距）")
        outside = scene.get("outside")
        if not isinstance(outside, list):
            errors.append(f"{prefix}.outside 必须是数组")
            outside = []
        if scene.get("type") == "主要" and len(outside) < 3:
            errors.append(f"{prefix} 是主要场景，outside 至少 3 轮（行动/阻碍/助力/转向）")
        inside = scene.get("inside")
        if not isinstance(inside, list) or not inside:
            errors.append(f"{prefix}.inside 不能为空（反应/消化/选择/决定）")
        if scene.get("scale") not in SCALES:
            errors.append(f"{prefix}.scale 必须是 {'/'.join(sorted(SCALES))}")
        if not _non_empty(scene.get("narration")):
            warnings.append(f"{prefix}.narration 为空：建议写清旁白或视角约束")

    curve = spec.get("tension_curve")
    if not isinstance(curve, list) or len(curve) < 2:
        errors.append("tension_curve 至少需要 2 个点")
        curve = []
    positions: list[int] = []
    for index, point in enumerate(curve, 1):
        prefix = f"tension_curve[{index}]"
        if not isinstance(point, dict):
            errors.append(f"{prefix} 必须是 object")
            continue
        position = point.get("position")
        value = point.get("value")
        if not isinstance(position, int) or not 0 <= position <= 100:
            errors.append(f"{prefix}.position 必须是 0-100 的整数")
        else:
            positions.append(position)
        if not isinstance(value, int) or not 1 <= value <= 10:
            errors.append(f"{prefix}.value 必须是 1-10 的整数")
    if positions and positions != sorted(positions):
        errors.append("tension_curve 必须按 position 升序")
    if positions and positions[0] > 10:
        warnings.append("tension_curve 缺少开场点（position <= 10）")
    if positions and positions[-1] < 90:
        warnings.append("tension_curve 缺少结尾点（position >= 90）")

    if spec.get("change") not in CHANGES:
        errors.append(f"change 必须是 {'/'.join(sorted(CHANGES))} 之一")
    if not isinstance(spec.get("new_hooks"), list):
        errors.append("new_hooks 必须是数组")

    return {
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "warnings": warnings,
    }


def to_scene_plan(spec: dict[str, Any]) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    for index, scene in enumerate(spec.get("scenes", []), 1):
        outside = scene.get("outside") if isinstance(scene.get("outside"), list) else []
        inside = scene.get("inside") if isinstance(scene.get("inside"), list) else []
        plan.append(
            {
                "title": str(scene.get("title") or f"场景{index}"),
                "target_word_count": int(scene.get("target_word_count", 0) or 0),
                "pov": str(scene.get("pov") or ""),
                "location": str(scene.get("location") or ""),
                "characters": list(scene.get("characters") or []),
                "goal": str(scene.get("goal") or ""),
                "conflict": str(scene.get("conflict") or " / ".join(outside)),
                "information_gain": str(scene.get("information_gain") or ""),
                "hook": str(scene.get("hook") or ""),
                "constraints": [
                    f"result: {scene.get('result', '')}",
                    f"outside: {' / '.join(str(item) for item in outside)}",
                    f"inside: {' / '.join(str(item) for item in inside)}",
                    f"scale: {scene.get('scale', '')}",
                    f"narration: {scene.get('narration', '')}",
                ],
                "outcome": str(scene.get("result") or ""),
            }
        )
    return plan


def _read_spec(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("spec 顶层必须是 object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="章节 / 场景 spec 工具")
    sub = parser.add_subparsers(dest="command", required=True)

    scaffold = sub.add_parser("scaffold", help="生成章节 spec 模板")
    scaffold.add_argument("--chapter", type=int, required=True)
    scaffold.add_argument("--title", default="")
    scaffold.add_argument("--output", required=True)
    scaffold.add_argument("--force", action="store_true")

    validate = sub.add_parser("validate", help="校验章节 spec")
    validate.add_argument("--file", required=True)
    validate.add_argument("--json", action="store_true")

    convert = sub.add_parser("to-scene-plan", help="转换为 scene_passport 场景计划")
    convert.add_argument("--file", required=True)
    convert.add_argument("--output", required=True)

    args = parser.parse_args()

    if args.command == "scaffold":
        output = Path(args.output).expanduser()
        if output.exists() and not args.force:
            print(f"error: 文件已存在: {output}（加 --force 覆盖）", file=sys.stderr)
            return 1
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(empty_spec(args.chapter, args.title), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"[OK] 已生成: {output}")
        return 0

    if args.command == "validate":
        try:
            spec = _read_spec(Path(args.file).expanduser())
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        report = validate_spec(spec)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(f"[{report['status'].upper()}] 章节 spec")
            for error in report["errors"]:
                print(f"[FAIL] {error}")
            for warning in report["warnings"]:
                print(f"[WARN] {warning}")
        return 0 if report["status"] == "pass" else 1

    if args.command == "to-scene-plan":
        try:
            spec = _read_spec(Path(args.file).expanduser())
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        output = Path(args.output).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(to_scene_plan(spec), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"[OK] 场景计划已生成: {output}")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
