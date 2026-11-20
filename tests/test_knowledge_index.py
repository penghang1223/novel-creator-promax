"""Knowledge index ranking: BM25 and route-directory boosts."""

from __future__ import annotations

import inspect
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from novel_creation_promax.core.knowledge_index import search_knowledge, sync_knowledge_index  # noqa: E402


class KnowledgeRankingTest(unittest.TestCase):
    def _doc(self, root: Path, relative: str, body: str) -> Path:
        path = root / "knowledge_base" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        return path

    def test_default_backend_is_bm25(self):
        signature = inspect.signature(search_knowledge)
        self.assertEqual(signature.parameters["backend"].default, "bm25")

    def test_bm25_prefers_focused_document_over_padded_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._doc(
                root,
                "40_Writing/01_开篇技巧/focused.md",
                "# 对话技法\n\n对话 交锋 对话 交锋 对话 交锋",
            )
            self._doc(
                root,
                "40_Writing/02_节奏与结构/padded.md",
                "# 杂项\n\n" + ("无关内容 " * 400) + "对话 交锋",
            )

            results = search_knowledge(
                root,
                "对话 交锋",
                limit=2,
                backend="bm25",
                include_prefixes=("knowledge_base/40_Writing",),
            )

            self.assertEqual(
                results[0]["path"],
                "knowledge_base/40_Writing/01_开篇技巧/focused.md",
            )

    def test_boost_prefix_reranks_selected_route_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            body = "# 开篇钩子\n\n开篇 钩子 开篇 钩子"
            self._doc(root, "40_Writing/02_节奏与结构/same.md", body)
            self._doc(root, "40_Writing/01_开篇技巧/boosted.md", body)

            results = search_knowledge(
                root,
                "开篇 钩子",
                limit=2,
                backend="bm25",
                boost_prefixes=("knowledge_base/40_Writing/01_开篇技巧",),
            )

            self.assertEqual(
                results[0]["path"],
                "knowledge_base/40_Writing/01_开篇技巧/boosted.md",
            )
            self.assertGreater(results[0]["boost"], 1.0)

    def test_exclude_paths_drops_already_selected_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            body = "# 开篇钩子\n\n开篇 钩子 开篇 钩子"
            self._doc(root, "40_Writing/01_开篇技巧/a.md", body)
            self._doc(root, "40_Writing/01_开篇技巧/b.md", body)

            results = search_knowledge(
                root,
                "开篇 钩子",
                limit=2,
                backend="bm25",
                exclude_paths=("knowledge_base/40_Writing/01_开篇技巧/a.md",),
            )

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["path"], "knowledge_base/40_Writing/01_开篇技巧/b.md")

    def test_sync_merges_plugin_and_workspace_knowledge(self):
        with tempfile.TemporaryDirectory() as plugin_tmp, tempfile.TemporaryDirectory() as ws_tmp:
            plugin = Path(plugin_tmp)
            workspace = Path(ws_tmp)
            craft = plugin / "knowledge_base" / "40_Writing" / "craft.md"
            craft.parent.mkdir(parents=True)
            craft.write_text("# 技法\n\n冲突 张力", encoding="utf-8")
            project_doc = workspace / "knowledge_base" / "80_Projects" / "书" / "_config.md"
            project_doc.parent.mkdir(parents=True)
            project_doc.write_text("# 项目\n\n冲突 张力", encoding="utf-8")

            root_keys = ("CLAUDE_PLUGIN_ROOT", "CLAUDE_PROJECT_DIR", "NOVEL_PLUGIN_ROOT", "NOVEL_WORKSPACE_ROOT")
            env = {key: value for key, value in os.environ.items() if key not in root_keys}
            env.update({"CLAUDE_PLUGIN_ROOT": str(plugin), "CLAUDE_PROJECT_DIR": str(workspace)})
            with mock.patch.dict(os.environ, env, clear=True):
                result = sync_knowledge_index(workspace)
                results = search_knowledge(
                    workspace,
                    "冲突 张力",
                    include_prefixes=("knowledge_base/40_Writing",),
                )

            self.assertGreaterEqual(result["documents"], 2)
            self.assertTrue(results)
            self.assertEqual(results[0]["path"], "knowledge_base/40_Writing/craft.md")

    def test_include_prefixes_excludes_other_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._doc(root, "40_Writing/01_开篇技巧/hit.md", "# 开篇\n\n开篇 钩子")
            self._doc(root, "60_Platform/platform.md", "# 平台\n\n开篇 钩子")

            results = search_knowledge(
                root,
                "开篇 钩子",
                backend="bm25",
                include_prefixes=("knowledge_base/40_Writing",),
            )

            self.assertTrue(results)
            self.assertTrue(all(item["path"].startswith("knowledge_base/40_Writing/") for item in results))


if __name__ == "__main__":
    unittest.main()
