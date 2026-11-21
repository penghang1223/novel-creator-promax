"""``init`` must scaffold workspace files that ``seal`` later requires.

A fresh install has no ``MEMORY.md``, ``.claude/memory/`` or
``knowledge_base/80_Projects/``. Without this scaffold, ``init → seal`` fails
on the first run even when the author did nothing wrong.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "novel_creation_promax" / "scripts" / "project_bootstrap_pipeline.py"
ROOT_ENV_KEYS = (
    "CLAUDE_PLUGIN_ROOT",
    "CLAUDE_PROJECT_DIR",
    "NOVEL_PLUGIN_ROOT",
    "NOVEL_WORKSPACE_ROOT",
    "NOVEL_PIPELINE_ACTIVE",
    "NOVEL_ALLOW_STATE_WRITE",
)
TITLE = "脚手架测试书"
REQUIRED_WORKSPACE_FILES = (
    "MEMORY.md",
    ".claude/memory/decisions/preferences.md",
    ".claude/memory/active_novels/progress.md",
    ".claude/memory/feedback/corrections.md",
    ".claude/memory/feedback/no-mer-names.md",
    "knowledge_base/80_Projects/脚手架测试书/_config.md",
)
PLACEHOLDERS = ("TODO", "TBD", "待填写", "待补充", "未填写", "未确定")


def run_init(workspace: Path) -> subprocess.CompletedProcess:
    env = {key: value for key, value in os.environ.items() if key not in ROOT_ENV_KEYS}
    env.update(
        {
            "CLAUDE_PLUGIN_ROOT": str(PROJECT_ROOT),
            "CLAUDE_PROJECT_DIR": str(workspace),
        }
    )
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "init",
            "--platform",
            "番茄",
            "--title",
            TITLE,
            "--genre",
            "都市",
            "--premise",
            "主角被裁员后觉醒能力，向前公司复仇。",
            "--confirm-workspace",
        ],
        text=True,
        capture_output=True,
        encoding="utf-8",
        env=env,
    )


class BootstrapWorkspaceScaffoldTest(unittest.TestCase):
    def test_init_creates_workspace_files_required_by_seal(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            result = run_init(workspace)
            self.assertEqual(result.returncode, 0, result.stderr)

            for relative in REQUIRED_WORKSPACE_FILES:
                with self.subTest(file=relative):
                    self.assertTrue((workspace / relative).is_file(), relative)

            config = workspace / "knowledge_base" / "80_Projects" / TITLE / "_config.md"
            text = config.read_text(encoding="utf-8").strip()
            self.assertGreaterEqual(len(text), 80)
            for token in PLACEHOLDERS:
                self.assertNotIn(token, text)

            self.assertIn(TITLE, (workspace / "MEMORY.md").read_text(encoding="utf-8"))

    def test_init_is_idempotent_for_memory_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self.assertEqual(run_init(workspace).returncode, 0)
            self.assertEqual(run_init(workspace).returncode, 0)

            text = (workspace / "MEMORY.md").read_text(encoding="utf-8")
            self.assertEqual(text.count(f"| {TITLE} |"), 1)

    def test_init_inserts_row_into_existing_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "MEMORY.md").write_text(
                "# MEMORY\n\n## 项目索引\n\n"
                "| 书名 | 平台 | 状态 | 项目目录 |\n"
                "|---|---|---|---|\n"
                "| 已有书 | 起点 | 连载中 | novel_output/起点/已有书 |\n\n"
                "## 共享规则\n\n- 规则\n",
                encoding="utf-8",
            )
            self.assertEqual(run_init(workspace).returncode, 0)

            text = (workspace / "MEMORY.md").read_text(encoding="utf-8")
            self.assertIn("| 已有书 |", text)
            self.assertIn(f"| {TITLE} |", text)
            self.assertLess(text.index(f"| {TITLE} |"), text.index("## 共享规则"))


if __name__ == "__main__":
    unittest.main()
