"""Centralized platform profile lookup for writing gates and reports."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .jsonio import load_json
from .roots import asset_path


FALLBACK_PROFILE: dict[str, Any] = {
    "aliases": [],
    "word_count_range": [2800, 3200],
    "recommended_range": [2800, 3200],
    "content_mode": "long_serial",
}


def load_profiles(project_root: Path | None = None) -> dict[str, Any]:
    if project_root is not None:
        candidate = project_root / "knowledge_base" / "60_Platform" / "_PROFILES.json"
        if candidate.is_file():
            payload = load_json(candidate, {})
            return payload if isinstance(payload, dict) else {}
    payload = load_json(asset_path("knowledge_base/60_Platform/_PROFILES.json"), {})
    return payload if isinstance(payload, dict) else {}


def normalize_platform(value: Any) -> str:
    text = str(value or "").strip()
    return {"番茄小说": "番茄", "知乎盐选": "知乎"}.get(text, text)


def platform_for_novel_dir(novel_dir: Path, *, state: dict[str, Any] | None = None) -> str:
    current = state if isinstance(state, dict) else load_json(novel_dir / "novel_state.json", {})
    if isinstance(current, dict):
        for key in ("target_platform", "platform"):
            value = normalize_platform(current.get(key))
            if value and value != "短篇小说":
                return value
    return normalize_platform(novel_dir.parent.name)


def _valid_range(value: Any, fallback: list[int]) -> list[int]:
    if isinstance(value, (list, tuple)) and len(value) == 2:
        try:
            low, high = int(value[0]), int(value[1])
            if 0 <= low <= high:
                return [low, high]
        except (TypeError, ValueError):
            pass
    return list(fallback)


def load_platform_profile(
    novel_dir: Path,
    *,
    project_root: Path | None = None,
    state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    profiles_payload = load_profiles(project_root)
    profiles = profiles_payload.get("profiles", {})
    platform = platform_for_novel_dir(novel_dir, state=state)
    selected: dict[str, Any] | None = None
    selected_name = platform
    if isinstance(profiles, dict):
        for name, profile in profiles.items():
            if not isinstance(profile, dict):
                continue
            aliases = [normalize_platform(item) for item in profile.get("aliases", [])]
            if normalize_platform(name) == platform or platform in aliases:
                selected = profile
                selected_name = name
                break
    if selected is None:
        selected = profiles_payload.get("default", FALLBACK_PROFILE)
    result = {**FALLBACK_PROFILE, **(selected if isinstance(selected, dict) else {})}
    result["platform"] = selected_name
    result["word_count_range"] = _valid_range(result.get("word_count_range"), FALLBACK_PROFILE["word_count_range"])
    result["recommended_range"] = _valid_range(result.get("recommended_range"), result["word_count_range"])
    return result


def evaluate_word_count(count: int, profile: dict[str, Any]) -> dict[str, Any]:
    low, high = profile["word_count_range"]
    recommended_low, recommended_high = profile["recommended_range"]
    return {
        "status": "pass" if low <= count <= high else "fail",
        "word_count": count,
        "gate_range": [low, high],
        "recommended_range": [recommended_low, recommended_high],
        "within_recommended_range": recommended_low <= count <= recommended_high,
    }
