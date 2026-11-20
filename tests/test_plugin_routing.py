"""插件模式下知识路由读插件资产、写工作区路径。"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from novel_creation_promax.core.knowledge_routes import (  # noqa: E402
    build_and_save_chapter_pack,
    build_knowledge_pack,
    chapter_outline_text,
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


class KnowledgePackPluginTest(unittest.TestCase):
    def test_reads_plugin_assets_and_workspace_outline(self):
        with tempfile.TemporaryDirectory() as plugin_tmp, tempfile.TemporaryDirectory() as workspace_tmp:
            plugin = Path(plugin_tmp)
            workspace = Path(workspace_tmp)

            constitution = plugin / "novel_creation_promax" / "references" / "writing_constitution.md"
            constitution.parent.mkdir(parents=True)
            constitution.write_text("# 写作宪法", encoding="utf-8")

            routes = {
                "schema_version": "1.0",
                "required": [
                    {
                        "key": "writing_constitution",
                        "scope": "plugin",
                        "path": "novel_creation_promax/references/writing_constitution.md",
                    },
                    {
                        "key": "outline",
                        "scope": "workspace",
                        "path": "novel_output/{平台}/{书名}/细纲",
                    },
                ],
                "routes": [],
            }
            (plugin / "knowledge_base").mkdir(parents=True)
            (plugin / "knowledge_base" / "_ROUTES.json").write_text(
                json.dumps(routes, ensure_ascii=False), encoding="utf-8"
            )

            novel_dir = workspace / "novel_output" / "番茄" / "书"
            (novel_dir / "细纲").mkdir(parents=True)
            (novel_dir / "细纲" / "第1章.md").write_text("章纲", encoding="utf-8")

            with clean_env(CLAUDE_PLUGIN_ROOT=str(plugin), CLAUDE_PROJECT_DIR=str(workspace)):
                pack = build_knowledge_pack(
                    project_root=workspace,
                    novel_dir=novel_dir,
                    chapter=1,
                    title="第1章",
                )

            self.assertEqual(pack["novel_dir"], "novel_output/番茄/书")
            required = {item["key"]: item for item in pack["required"]}
            self.assertTrue(required["writing_constitution"]["exists"])
            self.assertTrue(required["outline"]["exists"])


class EngineRouteSelectionTest(unittest.TestCase):
    def _build_pack(self, chapter: int, title: str, routes: list[dict]) -> dict:
        with tempfile.TemporaryDirectory() as plugin_tmp, tempfile.TemporaryDirectory() as workspace_tmp:
            plugin = Path(plugin_tmp)
            workspace = Path(workspace_tmp)
            (plugin / "knowledge_base").mkdir(parents=True)
            payload = {"schema_version": "1.0", "required": [], "routes": routes}
            (plugin / "knowledge_base" / "_ROUTES.json").write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
            for item in routes:
                for file_path in item.get("files", []):
                    target = plugin / file_path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text("# stub", encoding="utf-8")

            novel_dir = workspace / "novel_output" / "番茄" / "书"
            novel_dir.mkdir(parents=True)

            with clean_env(CLAUDE_PLUGIN_ROOT=str(plugin), CLAUDE_PROJECT_DIR=str(workspace)):
                return build_knowledge_pack(
                    project_root=workspace,
                    novel_dir=novel_dir,
                    chapter=chapter,
                    title=title,
                )

    def test_chapter_max_and_mod_select_engine_routes(self):
        routes = [
            {
                "key": "engine_opening",
                "name": "开篇100分卡",
                "chapter_max": 5,
                "files": ["knowledge_base/40_Writing/01_开篇技巧/开篇100分卡.md"],
            },
            {
                "key": "engine_continuity",
                "name": "六台账与跨章节奏",
                "chapter_mod": 5,
                "files": ["knowledge_base/30_Plot/六台账与20条毒点.md"],
            },
            {
                "key": "engine_deai",
                "name": "朱雀祛AI味",
                "title_keywords": ["AI", "去AI", "润色"],
                "files": ["knowledge_base/40_Writing/05_降AI痕迹/朱雀祛AI味五维.md"],
            },
        ]

        pack = self._build_pack(5, "第5章 AI 味重写", routes)
        selected = {item["key"]: item for item in pack["selected_routes"]}

        self.assertIn("engine_opening", selected)
        self.assertIn("engine_continuity", selected)
        self.assertIn("engine_deai", selected)
        self.assertTrue(all(file["exists"] for file in selected["engine_deai"]["files"]))

    def test_engine_routes_are_not_all_selected_every_chapter(self):
        routes = [
            {
                "key": "engine_opening",
                "name": "开篇100分卡",
                "chapter_max": 5,
                "files": ["knowledge_base/40_Writing/01_开篇技巧/开篇100分卡.md"],
            },
            {
                "key": "engine_continuity",
                "name": "六台账与跨章节奏",
                "chapter_mod": 5,
                "files": ["knowledge_base/30_Plot/六台账与20条毒点.md"],
            },
            {
                "key": "engine_deai",
                "name": "朱雀祛AI味",
                "title_keywords": ["AI", "去AI", "润色"],
                "files": ["knowledge_base/40_Writing/05_降AI痕迹/朱雀祛AI味五维.md"],
            },
        ]

        pack = self._build_pack(1, "第1章 开篇", routes)
        selected = {item["key"] for item in pack["selected_routes"]}

        self.assertEqual(selected, {"engine_opening"})


class KnowledgePackQualityTest(unittest.TestCase):
    def _workspace(self, root: Path) -> Path:
        workspace = root
        (workspace / "knowledge_base").mkdir(parents=True)
        return workspace

    def test_missing_selected_route_file_is_reported(self):
        with tempfile.TemporaryDirectory() as plugin_tmp, tempfile.TemporaryDirectory() as workspace_tmp:
            plugin = Path(plugin_tmp)
            workspace = self._workspace(Path(workspace_tmp))
            routes = {
                "schema_version": "1.0",
                "required": [],
                "routes": [
                    {
                        "key": "dialogue",
                        "name": "对话密集",
                        "files": [
                            "knowledge_base/40_Writing/03_人物与对话/不存在.md",
                            "knowledge_base/40_Writing/03_人物与对话/存在.md",
                        ],
                    }
                ],
            }
            (workspace / "knowledge_base" / "_ROUTES.json").write_text(
                json.dumps(routes, ensure_ascii=False), encoding="utf-8"
            )
            existing = workspace / "knowledge_base" / "40_Writing" / "03_人物与对话" / "存在.md"
            existing.parent.mkdir(parents=True, exist_ok=True)
            existing.write_text("# 对话技法\n\n交锋 对峙", encoding="utf-8")

            novel_dir = workspace / "novel_output" / "番茄" / "书"
            novel_dir.mkdir(parents=True)

            with clean_env(CLAUDE_PLUGIN_ROOT=str(plugin), CLAUDE_PROJECT_DIR=str(workspace)):
                pack = build_knowledge_pack(
                    project_root=workspace,
                    novel_dir=novel_dir,
                    chapter=1,
                    title="第1章 交锋",
                )

            self.assertEqual(pack["status"], "warning")
            self.assertIn(
                "knowledge_base/40_Writing/03_人物与对话/不存在.md",
                pack["missing_selected"],
            )
            self.assertNotIn(
                "knowledge_base/40_Writing/03_人物与对话/存在.md",
                pack["missing_selected"],
            )

    def test_outline_reader_supports_chinese_numeral_above_100(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel_dir = Path(tmp)
            (novel_dir / "细纲").mkdir()
            (novel_dir / "细纲" / "卷三.md").write_text(
                "## 第一百零五章 对峙\n\n高压对峙。\n\n## 第一百零六章 余波\n",
                encoding="utf-8",
            )
            text = chapter_outline_text(novel_dir, 105)
            self.assertIn("高压对峙", text)
            self.assertNotIn("第一百零六章", text)

    def test_outline_scene_tag_triggers_high_pressure_route(self):
        with tempfile.TemporaryDirectory() as plugin_tmp, tempfile.TemporaryDirectory() as workspace_tmp:
            plugin = Path(plugin_tmp)
            workspace = self._workspace(Path(workspace_tmp))
            routes = {
                "schema_version": "1.0",
                "required": [],
                "routes": [
                    {
                        "key": "high_pressure",
                        "name": "高压力/反派/暴露场景",
                        "files": ["knowledge_base/40_Writing/04_场景与描写/张力.md"],
                    }
                ],
            }
            (workspace / "knowledge_base" / "_ROUTES.json").write_text(
                json.dumps(routes, ensure_ascii=False), encoding="utf-8"
            )

            novel_dir = workspace / "novel_output" / "番茄" / "书"
            (novel_dir / "细纲").mkdir(parents=True)
            (novel_dir / "细纲" / "卷一.md").write_text(
                "# 卷一\n\n## 第3章 签字\n\n会议室高压对峙，反派逼迫主角签字。\n\n## 第4章 余波\n",
                encoding="utf-8",
            )

            with clean_env(CLAUDE_PLUGIN_ROOT=str(plugin), CLAUDE_PROJECT_DIR=str(workspace)):
                pack = build_knowledge_pack(
                    project_root=workspace,
                    novel_dir=novel_dir,
                    chapter=3,
                    title="第3章 签字",
                )

            selected = {item["key"]: item for item in pack["selected_routes"]}
            self.assertIn("high_pressure", selected)
            self.assertIn("细纲", selected["high_pressure"]["reason"])
            self.assertNotIn("第4章", pack["scene_text"])

    def test_route_stage_prioritizes_route_directory_before_fallback(self):
        with tempfile.TemporaryDirectory() as plugin_tmp, tempfile.TemporaryDirectory() as workspace_tmp:
            plugin = Path(plugin_tmp)
            workspace = self._workspace(Path(workspace_tmp))
            routes = {
                "schema_version": "1.0",
                "required": [],
                "routes": [
                    {
                        "key": "opening",
                        "name": "开篇章节",
                        "files": ["knowledge_base/40_Writing/01_开篇技巧/selected.md"],
                    }
                ],
            }
            (workspace / "knowledge_base" / "_ROUTES.json").write_text(
                json.dumps(routes, ensure_ascii=False), encoding="utf-8"
            )
            for relative, body in (
                ("40_Writing/01_开篇技巧/selected.md", "# 选中\n\n开篇 钩子"),
                ("40_Writing/01_开篇技巧/extra.md", "# 开篇补充\n\n开篇 钩子 开篇 钩子"),
                (
                    "40_Writing/02_节奏与结构/generic.md",
                    "# 节奏\n\n开篇 钩子 开篇 钩子 开篇 钩子 开篇 钩子",
                ),
            ):
                path = workspace / "knowledge_base" / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(body, encoding="utf-8")

            novel_dir = workspace / "novel_output" / "番茄" / "书"
            novel_dir.mkdir(parents=True)

            with clean_env(CLAUDE_PLUGIN_ROOT=str(plugin), CLAUDE_PROJECT_DIR=str(workspace)):
                pack = build_knowledge_pack(
                    project_root=workspace,
                    novel_dir=novel_dir,
                    chapter=2,
                    title="第2章 开篇",
                )

            results = pack["retrieval"]["results"]
            self.assertEqual(results[0]["path"], "knowledge_base/40_Writing/01_开篇技巧/extra.md")
            self.assertEqual(results[0]["stage"], "route")
            self.assertTrue(any(item["stage"] == "fallback" for item in results[1:]))
            self.assertNotIn("selected.md", [Path(item["path"]).name for item in results])

    def test_retrieval_excludes_metadata_and_limits_to_craft_dirs(self):
        with tempfile.TemporaryDirectory() as plugin_tmp, tempfile.TemporaryDirectory() as workspace_tmp:
            plugin = Path(plugin_tmp)
            workspace = self._workspace(Path(workspace_tmp))
            routes = {"schema_version": "1.0", "required": [], "routes": []}
            (workspace / "knowledge_base" / "_ROUTES.json").write_text(
                json.dumps(routes, ensure_ascii=False), encoding="utf-8"
            )
            (workspace / "knowledge_base" / "_ROUTING.md").write_text(
                "# 知识库路由表\n\n对话 都市 交锋 谈判", encoding="utf-8"
            )
            (workspace / "knowledge_base" / "40_Writing").mkdir(parents=True, exist_ok=True)
            routing_doc = workspace / "knowledge_base" / "40_Writing" / "写作知识路由表.md"
            routing_doc.write_text("# 写作知识路由表\n\n对话 都市 交锋 谈判", encoding="utf-8")
            craft = workspace / "knowledge_base" / "40_Writing" / "03_人物与对话" / "对话技法.md"
            craft.parent.mkdir(parents=True, exist_ok=True)
            craft.write_text(
                "# 对话技法\n\n都市 对话 交锋 谈判 对话 交锋 谈判",
                encoding="utf-8",
            )

            novel_dir = workspace / "novel_output" / "番茄" / "书"
            novel_dir.mkdir(parents=True)
            (novel_dir / "novel_state.json").write_text(
                json.dumps({"genre": "都市"}, ensure_ascii=False), encoding="utf-8"
            )

            with clean_env(CLAUDE_PLUGIN_ROOT=str(plugin), CLAUDE_PROJECT_DIR=str(workspace)):
                pack = build_knowledge_pack(
                    project_root=workspace,
                    novel_dir=novel_dir,
                    chapter=2,
                    title="第2章 对话交锋",
                )

            results = pack["retrieval"]["results"]
            self.assertEqual(pack["retrieval"]["mode"], "bm25")
            self.assertTrue(results)
            for item in results:
                self.assertTrue(
                    item["path"].startswith(
                        ("knowledge_base/20_Characters", "knowledge_base/30_Plot", "knowledge_base/40_Writing")
                    ),
                    item["path"],
                )
                self.assertNotIn("_ROUTING.md", item["path"])
                self.assertNotIn("写作知识路由表.md", item["path"])

    def test_strict_knowledge_gate_blocks_and_warn_mode_does_not(self):
        with tempfile.TemporaryDirectory() as plugin_tmp, tempfile.TemporaryDirectory() as workspace_tmp:
            plugin = Path(plugin_tmp)
            workspace = self._workspace(Path(workspace_tmp))
            routes = {
                "schema_version": "1.0",
                "required": [],
                "routes": [
                    {"key": "genre", "name": "题材特化", "files": ["knowledge_base/10_WorldBuilding/题材知识库/都市.md"]}
                ],
            }
            (workspace / "knowledge_base" / "_ROUTES.json").write_text(
                json.dumps(routes, ensure_ascii=False), encoding="utf-8"
            )
            novel_dir = workspace / "novel_output" / "番茄" / "书"
            (novel_dir / "摘要").mkdir(parents=True)
            (novel_dir / "novel_state.json").write_text(
                json.dumps({"genre": "都市"}, ensure_ascii=False), encoding="utf-8"
            )

            with clean_env(CLAUDE_PLUGIN_ROOT=str(plugin), CLAUDE_PROJECT_DIR=str(workspace)):
                warn = build_and_save_chapter_pack(
                    project_root=workspace, novel_dir=novel_dir, chapter=1, title="第1章"
                )
                self.assertEqual(warn["status"], "warning")
                self.assertIn(
                    "knowledge_base/10_WorldBuilding/题材知识库/都市.md",
                    warn["missing_selected"],
                )

                strict = build_and_save_chapter_pack(
                    project_root=workspace,
                    novel_dir=novel_dir,
                    chapter=1,
                    title="第1章",
                    strict=True,
                )
                self.assertEqual(strict["status"], "fail")


if __name__ == "__main__":
    unittest.main()
