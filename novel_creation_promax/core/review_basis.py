"""Review basis: bind a review to the exact inputs the reviewer read.

The chapter revision is already bound by ``target.revision_id``. This module
adds the other review inputs that can silently change:

- ``rule_stack`` (compiled truth constraints)
- ``truth_brief`` (human-readable truth summary)
- ``taskbook`` (context-agent's five-section brief)
- ``memory_pack`` (chapter memory pack)

Raw truth files and the passport are deliberately excluded: ``post:truth``
changes truth files after the review, and the passport changes in every post
phase. Including them would make a valid review stale during its own pipeline
run. The compiled ``rule_stack`` and ``truth_brief`` are the reviewer's actual
constraints, so they are the correct boundary.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .chapter_commit import sha256_file
from .paths import find_chapter_file, rel

BASIS_WORKFLOW = "novel-creator:chapter-write"
BASIS_STEP = "review"
BASIS_SCHEMA_ID = "chapter_review"
BASIS_SCHEMA_VERSION = 1
BASIS_PROMPT_VERSION = 1


def _resource(
    resource_type: str,
    resource_id: str,
    path: Path,
    novel_dir: Path,
    *,
    required: bool = False,
) -> dict[str, Any]:
    exists = path.is_file()
    return {
        "resource_type": resource_type,
        "id": resource_id,
        "path": rel(path, novel_dir),
        "exists": exists,
        "required": required,
        "sha256": sha256_file(path) if exists else "",
        "size": path.stat().st_size if exists else 0,
    }


def _missing_resource(resource_type: str, resource_id: str, *, required: bool) -> dict[str, Any]:
    return {
        "resource_type": resource_type,
        "id": resource_id,
        "path": "",
        "exists": False,
        "required": required,
        "sha256": "",
        "size": 0,
    }


def collect_review_resources(novel_dir: Path, chapter: int) -> list[dict[str, Any]]:
    """Collect the artifacts a chapter review actually depends on."""
    resources: list[dict[str, Any]] = []

    chapter_file = find_chapter_file(novel_dir, chapter)
    if chapter_file is None:
        resources.append(_missing_resource("chapter", f"{chapter:03d}", required=True))
    else:
        resources.append(
            _resource("chapter", f"{chapter:03d}", chapter_file, novel_dir, required=True)
        )

    rule_stack = novel_dir / "摘要" / f"chapter_{chapter:03d}_rule_stack.json"
    resources.append(
        _resource("rule_stack", f"{chapter:03d}", rule_stack, novel_dir, required=True)
    )

    for resource_type, path in (
        ("truth_brief", novel_dir / "素材" / f"chapter_{chapter:03d}_truth_brief.md"),
        ("taskbook", novel_dir / "摘要" / f"chapter_{chapter:03d}_taskbook.md"),
        ("memory_pack", novel_dir / "摘要" / f"chapter_{chapter:03d}_pack.json"),
    ):
        resources.append(_resource(resource_type, f"{chapter:03d}", path, novel_dir))
    return resources


def _version_map(resources: list[dict[str, Any]]) -> dict[str, str]:
    return {
        f"{item['resource_type']}:{item['id']}": str(item.get("sha256") or "")
        for item in resources
    }


def _fingerprint(basis: dict[str, Any]) -> str:
    canonical = json.dumps(
        {
            "workflow": basis["workflow"],
            "step": basis["step"],
            "schema_id": basis["schema_id"],
            "schema_version": basis["schema_version"],
            "prompt_version": basis["prompt_version"],
            "source_refs": basis["source_refs"],
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_review_basis(novel_dir: Path, chapter: int) -> dict[str, Any]:
    """Return the canonical ``basis`` and ``expected_versions`` bundle."""
    resources = collect_review_resources(novel_dir, chapter)
    basis = {
        "workflow": BASIS_WORKFLOW,
        "step": BASIS_STEP,
        "schema_id": BASIS_SCHEMA_ID,
        "schema_version": BASIS_SCHEMA_VERSION,
        "prompt_version": BASIS_PROMPT_VERSION,
        "source_refs": resources,
    }
    basis["input_fingerprint"] = _fingerprint(basis)
    return {
        "basis": basis,
        "expected_versions": _version_map(resources),
    }


def expected_versions_from_basis(basis: Any) -> dict[str, str]:
    if not isinstance(basis, dict):
        return {}
    refs = basis.get("source_refs")
    if not isinstance(refs, list):
        return {}
    result: dict[str, str] = {}
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        resource_type = str(ref.get("resource_type") or "")
        resource_id = str(ref.get("id") or "")
        if resource_type and resource_id:
            result[f"{resource_type}:{resource_id}"] = str(ref.get("sha256") or "")
    return result


def review_basis_gate(novel_dir: Path, chapter: int, payload: Any) -> dict[str, Any]:
    """Compare a review's basis against the current inputs."""
    result: dict[str, Any] = {
        "status": "pass",
        "errors": [],
        "warnings": [],
        "checked": 0,
        "current_fingerprint": "",
    }
    if not isinstance(payload, dict):
        result["status"] = "invalid"
        result["errors"].append("review payload 必须是对象")
        return result

    basis = payload.get("basis")
    expected = payload.get("expected_versions")
    if not basis and not expected:
        result["warnings"].append(
            "未绑定 basis；建议 target --with-basis 后重新审稿"
        )
        return result

    current = build_review_basis(novel_dir, chapter)
    current_versions = current["expected_versions"]
    result["current_fingerprint"] = current["basis"]["input_fingerprint"]

    if isinstance(expected, dict) and expected:
        for key, value in expected.items():
            result["checked"] += 1
            actual = current_versions.get(key)
            if actual is None:
                result["errors"].append(f"basis 引用的资源当前不存在: {key}")
                continue
            if str(value) != actual:
                result["errors"].append(
                    f"review basis 已过期: {key} (expected={value}, actual={actual})"
                )
    elif isinstance(basis, dict):
        for key, value in expected_versions_from_basis(basis).items():
            result["checked"] += 1
            actual = current_versions.get(key)
            if actual is None or value != actual:
                result["errors"].append(
                    f"review basis 已过期: {key} (expected={value or '<missing>'}, actual={actual or '<missing>'})"
                )

    fingerprint = ""
    if isinstance(basis, dict):
        fingerprint = str(basis.get("input_fingerprint") or "")
    if (
        fingerprint
        and fingerprint != current["basis"]["input_fingerprint"]
        and not result["errors"]
    ):
        result["errors"].append(
            "review basis input_fingerprint 与当前输入不一致"
        )

    result["status"] = "stale" if result["errors"] else "pass"
    return result
