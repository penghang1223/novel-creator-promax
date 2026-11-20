"""双根路径解析器测试（插件资产 vs 用户工作区）。"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from novel_creation_promax.core import roots  # noqa: E402

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


class PluginRootTest(unittest.TestCase):
    def test_prefers_claude_plugin_root(self):
        with tempfile.TemporaryDirectory() as tmp, clean_env(CLAUDE_PLUGIN_ROOT=tmp):
            self.assertEqual(roots.plugin_root(), Path(tmp).resolve())

    def test_falls_back_to_repository_root(self):
        with clean_env():
            self.assertTrue((roots.plugin_root() / "novel_creation_promax").is_dir())


class WorkspaceRootTest(unittest.TestCase):
    def test_prefers_novel_workspace_root(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as other, clean_env(
            NOVEL_WORKSPACE_ROOT=tmp, CLAUDE_PROJECT_DIR=other
        ):
            self.assertEqual(roots.workspace_root(), Path(tmp).resolve())

    def test_falls_back_to_claude_project_dir(self):
        with tempfile.TemporaryDirectory() as tmp, clean_env(CLAUDE_PROJECT_DIR=tmp):
            self.assertEqual(roots.workspace_root(), Path(tmp).resolve())

    def test_falls_back_to_plugin_root(self):
        with tempfile.TemporaryDirectory() as tmp, clean_env(CLAUDE_PLUGIN_ROOT=tmp):
            self.assertEqual(roots.workspace_root(), Path(tmp).resolve())


class AssetResolutionTest(unittest.TestCase):
    def test_asset_path_uses_plugin_root(self):
        with tempfile.TemporaryDirectory() as plugin, tempfile.TemporaryDirectory() as workspace, clean_env(
            CLAUDE_PLUGIN_ROOT=plugin, CLAUDE_PROJECT_DIR=workspace
        ):
            self.assertEqual(
                roots.asset_path("knowledge_base/_ROUTES.json"),
                Path(plugin).resolve() / "knowledge_base" / "_ROUTES.json",
            )

    def test_workspace_knowledge_base_overrides_plugin(self):
        with tempfile.TemporaryDirectory() as plugin, tempfile.TemporaryDirectory() as workspace, clean_env(
            CLAUDE_PLUGIN_ROOT=plugin, CLAUDE_PROJECT_DIR=workspace
        ):
            override = Path(workspace) / "knowledge_base" / "_ROUTES.json"
            override.parent.mkdir(parents=True)
            override.write_text("{}", encoding="utf-8")

            self.assertEqual(roots.asset_path("knowledge_base/_ROUTES.json"), override.resolve())

    def test_workspace_path_uses_workspace_root(self):
        with tempfile.TemporaryDirectory() as workspace, clean_env(CLAUDE_PROJECT_DIR=workspace):
            self.assertEqual(
                roots.workspace_path("novel_output/番茄/书"),
                Path(workspace).resolve() / "novel_output" / "番茄" / "书",
            )


class RouteResolutionTest(unittest.TestCase):
    def test_infers_workspace_routes(self):
        with tempfile.TemporaryDirectory() as plugin, tempfile.TemporaryDirectory() as workspace, clean_env(
            CLAUDE_PLUGIN_ROOT=plugin, CLAUDE_PROJECT_DIR=workspace
        ):
            for value in ("novel_output/番茄/书/细纲", ".claude/memory/x.md", "MEMORY.md"):
                self.assertEqual(
                    roots.resolve_route_path(value),
                    Path(workspace).resolve() / value,
                    value,
                )

    def test_infers_plugin_routes(self):
        with tempfile.TemporaryDirectory() as plugin, tempfile.TemporaryDirectory() as workspace, clean_env(
            CLAUDE_PLUGIN_ROOT=plugin, CLAUDE_PROJECT_DIR=workspace
        ):
            for value in ("novel_creation_promax/references/x.md", "knowledge_base/50_Quality/x.md"):
                self.assertEqual(
                    roots.resolve_route_path(value),
                    Path(plugin).resolve() / value,
                    value,
                )

    def test_explicit_scope_wins(self):
        with tempfile.TemporaryDirectory() as plugin, tempfile.TemporaryDirectory() as workspace, clean_env(
            CLAUDE_PLUGIN_ROOT=plugin, CLAUDE_PROJECT_DIR=workspace
        ):
            self.assertEqual(
                roots.resolve_route_path("novel_output/书", scope="plugin"),
                Path(plugin).resolve() / "novel_output" / "书",
            )
            self.assertEqual(
                roots.resolve_route_path("knowledge_base/x.md", scope="workspace"),
                Path(workspace).resolve() / "knowledge_base" / "x.md",
            )

    def test_absolute_path_passthrough(self):
        with clean_env():
            absolute = Path("/tmp/absolute-route.md")
            self.assertEqual(roots.resolve_route_path(str(absolute)), absolute.resolve())


if __name__ == "__main__":
    unittest.main()
