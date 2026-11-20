"""Optional scene-level planning and review passports."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .jsonio import load_json, now_iso, save_json
from .passport import load_passport, passport_path, save_passport


SCENE_SCHEMA_VERSION = "1.0"
SCENE_STATUSES = ("planning", "draft", "audit", "pass", "blocked")
SCENE_ROOT = Path("素材") / "scenes"


def scene_dir(novel_dir: Path, chapter: int) -> Path:
    return novel_dir / SCENE_ROOT / f"chapter_{chapter:03d}"


def scene_passport_path(novel_dir: Path, chapter: int, scene: int) -> Path:
    return scene_dir(novel_dir, chapter) / f"scene_{scene:03d}_passport.json"


def init_scene_passport(chapter: int, scene: int, spec: dict[str, Any] | None = None) -> dict[str, Any]:
    details = spec if isinstance(spec, dict) else {}
    title = str(details.get("title") or f"场景{scene}")
    return {
        "schema_version": SCENE_SCHEMA_VERSION,
        "scene_id": f"ch{chapter:03d}-s{scene:03d}",
        "chapter": chapter,
        "scene": scene,
        "title": title,
        "status": str(details.get("status") or "planning"),
        "target_word_count": int(details.get("target_word_count", 0) or 0),
        "pov": str(details.get("pov") or ""),
        "location": str(details.get("location") or ""),
        "characters": list(details.get("characters") or []),
        "goal": str(details.get("goal") or ""),
        "conflict": str(details.get("conflict") or ""),
        "information_gain": str(details.get("information_gain") or ""),
        "hook": str(details.get("hook") or ""),
        "constraints": list(details.get("constraints") or []),
        "outcome": str(details.get("outcome") or ""),
        "attempts": {},
        "error": "",
        "updated_at": now_iso(),
    }


def ensure_scene_shape(value: Any, chapter: int, scene: int) -> dict[str, Any]:
    base = init_scene_passport(chapter, scene)
    current = value if isinstance(value, dict) else {}
    result = {**base, **current}
    result["schema_version"] = SCENE_SCHEMA_VERSION
    result["chapter"] = chapter
    result["scene"] = scene
    result["scene_id"] = f"ch{chapter:03d}-s{scene:03d}"
    result["attempts"] = dict(current.get("attempts", {})) if isinstance(current.get("attempts"), dict) else {}
    return result


def load_scene_passport(novel_dir: Path, chapter: int, scene: int) -> dict[str, Any]:
    path = scene_passport_path(novel_dir, chapter, scene)
    return ensure_scene_shape(load_json(path, {}), chapter, scene)


def save_scene_passport(novel_dir: Path, payload: dict[str, Any]) -> Path:
    chapter = int(payload["chapter"])
    scene = int(payload["scene"])
    payload = ensure_scene_shape(payload, chapter, scene)
    payload["updated_at"] = now_iso()
    path = scene_passport_path(novel_dir, chapter, scene)
    save_json(path, payload)
    return path


def initialize_scene_plan(novel_dir: Path, chapter: int, plan: list[dict[str, Any]]) -> dict[str, Any]:
    if not plan:
        raise ValueError("场景计划不能为空")
    for index, spec in enumerate(plan, start=1):
        if not isinstance(spec, dict):
            raise ValueError(f"第{index}个场景计划不是对象")
        payload = load_scene_passport(novel_dir, chapter, index)
        payload.update(spec)
        payload["chapter"] = chapter
        payload["scene"] = index
        save_scene_passport(novel_dir, payload)
    return sync_chapter_scene_index(novel_dir, chapter)


def transition_scene(
    novel_dir: Path,
    chapter: int,
    scene: int,
    status: str,
    *,
    error: str = "",
) -> dict[str, Any]:
    if status not in SCENE_STATUSES:
        raise ValueError(f"未知场景状态: {status}")
    payload = load_scene_passport(novel_dir, chapter, scene)
    payload["attempts"][status] = int(payload["attempts"].get(status, 0) or 0) + 1
    payload["status"] = status
    payload["error"] = error
    save_scene_passport(novel_dir, payload)
    sync_chapter_scene_index(novel_dir, chapter)
    return payload


def list_scene_passports(novel_dir: Path, chapter: int) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for path in sorted(scene_dir(novel_dir, chapter).glob("scene_*_passport.json")):
        payload = load_json(path, {})
        if not isinstance(payload, dict):
            continue
        scene = int(payload.get("scene", 0) or 0)
        if scene:
            results.append(ensure_scene_shape(payload, chapter, scene))
    return sorted(results, key=lambda item: item["scene"])


def sync_chapter_scene_index(novel_dir: Path, chapter: int) -> dict[str, Any]:
    scenes = list_scene_passports(novel_dir, chapter)
    passed = sum(1 for item in scenes if item["status"] == "pass")
    blocked = sum(1 for item in scenes if item["status"] == "blocked")
    next_scene = next((item["scene"] for item in scenes if item["status"] != "pass"), 0)
    status = "pass" if scenes and passed == len(scenes) else "blocked" if blocked else "pending"
    summary = {
        "enabled": bool(scenes),
        "count": len(scenes),
        "passed": passed,
        "blocked": blocked,
        "next_scene": next_scene,
        "status": status,
        "path": str(scene_dir(novel_dir, chapter).relative_to(novel_dir).as_posix()),
        "updated_at": now_iso(),
    }
    passport = load_passport(novel_dir, chapter, chapter_file=None)
    passport["scene_index"] = summary
    save_passport(novel_dir, chapter, passport)
    return summary
