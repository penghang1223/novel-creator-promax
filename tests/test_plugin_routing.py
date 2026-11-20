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

from novel_creation_promax.core.knowledge_routes import build_knowledge_pack  # noqa: E402

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


if __name__ == "__main__":
    unittest.main()
