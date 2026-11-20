"""Quality-mode contracts for deterministic and human/agent-assisted review."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .jsonio import load_json


QUALITY_MODES = ("deterministic", "balanced", "tribunal")
QUALITY_PROFILES: dict[str, dict[str, Any]] = {
    "deterministic": {
        "label": "确定性门禁",
        "requires_quality_review": False,
        "description": "只运行脚本门禁和结构化检查。",
    },
    "balanced": {
        "label": "确定性 + 抽审",
        "requires_quality_review": False,
        "description": "保留确定性门禁，可附加人工或单模型审稿报告。",
    },
    "tribunal": {
        "label": "仲裁审稿",
        "requires_quality_review": True,
        "description": "必须存在人工确认后的 quality_review 报告才允许 commit。",
    },
}


def resolve_quality_mode(novel_dir: Path, requested: str = "") -> str:
    if requested in QUALITY_MODES:
        return requested
    state = load_json(novel_dir / "novel_state.json", {})
    configured = state.get("quality_mode") if isinstance(state, dict) else ""
    return configured if configured in QUALITY_MODES else "deterministic"


def quality_profile(novel_dir: Path, requested: str = "") -> tuple[str, dict[str, Any]]:
    mode = resolve_quality_mode(novel_dir, requested)
    return mode, dict(QUALITY_PROFILES[mode])


def quality_review_path(novel_dir: Path, chapter: int) -> Path:
    return novel_dir / "素材" / f"quality_review_ch{chapter:03d}.json"
