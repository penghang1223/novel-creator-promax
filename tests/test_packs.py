"""Capability packs: selection, route expansion and manifest validation."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from novel_creation_promax.core.knowledge_routes import (  # noqa: E402
    build_knowledge_pack,
    load_packs,
    select_pack,
)

ROOT_ENV_KEYS = (
    "CLAUDE_PLUGIN_ROOT",
    "CLAUDE_PROJECT_DIR",
    "NOVEL_PLUGIN_ROOT",
    "NOVEL_WORKSPACE_ROOT",
)


def clean_env(**values: str):
    env = {key: value for key, value in os.environ.items() if key not in ROOT_ENV_KEYS}
    env.update(values)
    return mock.patch.dict(os.environ, env, clear=True)


def make_workspace(root: Path, *, platform: str = "番茄", genre: str = "现言") -> Path:
    workspace = root
    (workspace / "knowledge_base").mkdir(parents=True, exist_ok=True)
    (workspace / "knowledge_base" / "_ROUTES.json").write_text(
        json.dumps({"schema_version": "1.0", "required": [], "routes": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    novel_dir = workspace / "novel_output" / platform / "书"
    novel_dir.mkdir(parents=True)
    (novel_dir / "novel_state.json").write_text(
        json.dumps({"platform": platform, "genre": genre}, ensure_ascii=False),
        encoding="utf-8",
    )
    return novel_dir


def write_pack(workspace: Path, pack_id: str = "test-pack") -> Path:
    pack_dir = workspace / "knowledge_base" / "packs" / pack_id
    pack_dir.mkdir(parents=True)
    (pack_dir / "pitfalls.md").write_text("# 测试坑点库\n", encoding="utf-8")
    doc = workspace / "knowledge_base" / "40_Writing" / "dialogue.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text("# 对话\n\n交锋与潜台词。", encoding="utf-8")
    (pack_dir / "pack.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "pack_id": pack_id,
                "version": "1.0.0",
                "display_name": "测试包",
                "signals": {"platform": "番茄", "genre_tags": ["现言", "婚恋"]},
                "capabilities": ["dialogue_heavy"],
                "routes": {
                    "dialogue": {
                        "name": "对话密集",
                        "trigger_capabilities": ["dialogue_heavy"],
                        "files": ["knowledge_base/40_Writing/dialogue.md"],
                    }
                },
                "pitfalls": "pitfalls.md",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return pack_dir


class PackSelectionTest(unittest.TestCase):
    def test_selects_pack_by_platform_and_genre(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            write_pack(workspace)
            whole = make_workspace(workspace, platform="番茄", genre="现言职场")
            with clean_env(CLAUDE_PLUGIN_ROOT=str(PROJECT_ROOT), CLAUDE_PROJECT_DIR=str(workspace)):
                packs = load_packs(workspace)
                selected = select_pack(whole, packs)
            self.assertIsNotNone(selected)
            self.assertEqual(selected["pack_id"], "test-pack")

    def test_explicit_pack_id_wins_over_signals(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            write_pack(workspace)
            novel_dir = make_workspace(workspace, platform="起点", genre="玄幻")
            state = json.loads((novel_dir / "novel_state.json").read_text(encoding="utf-8"))
            state["pack_id"] = "test-pack"
            (novel_dir / "novel_state.json").write_text(
                json.dumps(state, ensure_ascii=False), encoding="utf-8"
            )
            with clean_env(CLAUDE_PLUGIN_ROOT=str(PROJECT_ROOT), CLAUDE_PROJECT_DIR=str(workspace)):
                selected = select_pack(novel_dir, load_packs(workspace))
            self.assertIsNotNone(selected)
            self.assertEqual(selected["pack_id"], "test-pack")

    def test_capability_triggers_route_without_title_keyword(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            write_pack(workspace)
            novel_dir = make_workspace(workspace, platform="番茄", genre="现言")
            with clean_env(CLAUDE_PLUGIN_ROOT=str(PROJECT_ROOT), CLAUDE_PROJECT_DIR=str(workspace)):
                pack = build_knowledge_pack(
                    project_root=workspace,
                    novel_dir=novel_dir,
                    chapter=2,
                    title="第2章 平常的一天",
                )
            self.assertEqual(pack["pack"]["pack_id"], "test-pack")
            selected = {item["key"]: item for item in pack["selected_routes"]}
            self.assertIn("dialogue", selected)
            self.assertEqual(selected["dialogue"].get("source"), "pack")
            self.assertTrue(selected["dialogue"]["files"][0]["exists"])

    def test_no_matching_pack_falls_back_to_routes(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            write_pack(workspace)
            novel_dir = make_workspace(workspace, platform="七猫", genre="悬疑")
            with clean_env(CLAUDE_PLUGIN_ROOT=str(PROJECT_ROOT), CLAUDE_PROJECT_DIR=str(workspace)):
                pack = build_knowledge_pack(
                    project_root=workspace,
                    novel_dir=novel_dir,
                    chapter=2,
                    title="第2章 平常的一天",
                )
            self.assertEqual(pack["pack"], {})
            self.assertNotIn(
                "dialogue",
                {item["key"] for item in pack["selected_routes"]},
            )


class PackManifestTest(unittest.TestCase):
    def test_repository_packs_pass_manifest_check(self):
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "tools" / "pack_check.py"), "--json"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["passed"])
        self.assertIn("fanqie-female-romance", payload["packs"])
        self.assertIn("qidian-male-fantasy", payload["packs"])
        self.assertIn("zhihu-short-story", payload["packs"])


if __name__ == "__main__":
    unittest.main()
