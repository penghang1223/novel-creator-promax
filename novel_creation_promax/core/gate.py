"""Bootstrap gate verification.

``novel_state.json.workflow_gate.can_write_chapter`` 是普通 JSON，任何脚本或
agent 都能手改。为了让"立项门禁"具备可校验性，``seal`` 会同时写入

    workflow_gate.bootstrap_report        -> 报告相对路径
    workflow_gate.bootstrap_report_sha256 -> 报告文件指纹

本模块负责复核这三者是否自洽。历史项目可能还没有指纹字段，此时退化为
"报告存在且标记通过"，并给出需要重跑 seal 的提示。
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .jsonio import load_json


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_gate_state(novel_dir: Path) -> dict[str, Any]:
    state = load_json(novel_dir / "novel_state.json", {})
    if not isinstance(state, dict):
        return {}
    gate = state.get("workflow_gate")
    return gate if isinstance(gate, dict) else {}


def verify_bootstrap_gate(novel_dir: Path) -> tuple[bool, str]:
    """返回 (是否允许写正文, 说明)。"""
    gate = load_gate_state(novel_dir)
    if not gate:
        return False, "novel_state.json 缺少 workflow_gate"

    if gate.get("can_write_chapter") is not True:
        return False, "workflow_gate.can_write_chapter 不为 true（需运行 seal）"

    report_rel = str(gate.get("bootstrap_report") or "").strip()
    if not report_rel:
        return False, "workflow_gate 缺少 bootstrap_report，无法校验门禁报告"

    report_path = novel_dir / report_rel
    if not report_path.exists():
        return False, f"门禁报告不存在: {report_rel}"

    expected = str(gate.get("bootstrap_report_sha256") or "").strip()
    if expected:
        actual = sha256_file(report_path)
        if actual != expected:
            return False, (
                "门禁报告指纹不匹配（报告被重新生成或被手改）。"
                "请重新运行 seal 并记录新指纹。"
            )
    else:
        # 历史项目兼容：无指纹时只能校验报告内容本身
        report = load_json(report_path, {})
        if not isinstance(report, dict) or not report.get("can_write_chapter"):
            return False, f"门禁报告未标记通过: {report_rel}"
        return True, f"立项门禁通过（legacy，无指纹校验，建议重跑 seal）: {report_rel}"

    report = load_json(report_path, {})
    if not isinstance(report, dict) or not report.get("can_write_chapter"):
        return False, f"门禁报告未标记通过: {report_rel}"
    return True, f"立项门禁通过（指纹已校验）: {report_rel}"
