#!/usr/bin/env python3
"""Validate knowledge_base/packs/*/pack.json and their referenced files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from novel_creation_promax.core.jsonio import load_json  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="校验能力包 manifest")
    parser.add_argument("--root", default=str(PROJECT_ROOT), help="项目根目录")
    parser.add_argument("--json", action="store_true", help="输出 JSON 报告")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    packs_root = root / "knowledge_base" / "packs"
    errors: list[str] = []
    packs: list[str] = []

    if not packs_root.is_dir():
        errors.append(f"能力包目录不存在: {packs_root}")

    for path in sorted(packs_root.glob("*/pack.json")) if packs_root.is_dir() else []:
        payload = load_json(path, {})
        if not isinstance(payload, dict):
            errors.append(f"{path.relative_to(root)}: 不是对象")
            continue
        pack_id = str(payload.get("pack_id") or "")
        if pack_id != path.parent.name:
            errors.append(f"{path.relative_to(root)}: pack_id={pack_id!r} 与目录名不一致")
            continue
        packs.append(pack_id)
        for key in ("schema_version", "version", "display_name"):
            if not payload.get(key):
                errors.append(f"{pack_id}: 缺少 {key}")
        signals = payload.get("signals")
        if not isinstance(signals, dict) or not signals.get("platform"):
            errors.append(f"{pack_id}: signals.platform 缺失")
        capabilities = payload.get("capabilities")
        if not isinstance(capabilities, list) or not capabilities:
            errors.append(f"{pack_id}: capabilities 必须是非空数组")
        routes = payload.get("routes")
        if not isinstance(routes, dict) or not routes:
            errors.append(f"{pack_id}: routes 必须是非空对象")
        else:
            for key, route in routes.items():
                if not isinstance(route, dict):
                    errors.append(f"{pack_id}.routes.{key}: 不是对象")
                    continue
                files = route.get("files")
                if not isinstance(files, list) or not files:
                    errors.append(f"{pack_id}.routes.{key}: files 必须是非空数组")
                    continue
                for relative in files:
                    if not isinstance(relative, str) or not relative:
                        errors.append(f"{pack_id}.routes.{key}: 文件路径为空")
                    elif not (root / relative).is_file():
                        errors.append(f"{pack_id}.routes.{key}: 文件不存在 {relative}")
        pitfalls = payload.get("pitfalls")
        if not isinstance(pitfalls, str) or not (path.parent / pitfalls).is_file():
            errors.append(f"{pack_id}: pitfalls 不存在 {pitfalls}")

    report = {"packs": packs, "errors": errors, "passed": not errors}
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"能力包检查: {len(packs)} 个包，{len(errors)} 个错误")
        for item in errors:
            print(f"  [FAIL] {item}")
        if not errors:
            print("  PASS")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
