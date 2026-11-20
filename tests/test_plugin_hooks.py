"""Plugin hooks: runtime write guard and session status."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HOOKS = PROJECT_ROOT / "hooks"
ROOT_ENV_KEYS = (
    "CLAUDE_PLUGIN_ROOT",
    "CLAUDE_PROJECT_DIR",
    "NOVEL_PLUGIN_ROOT",
    "NOVEL_WORKSPACE_ROOT",
    "NOVEL_PIPELINE_ACTIVE",
    "NOVEL_ALLOW_STATE_WRITE",
)


def hook_env(workspace: Path, **values: str) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if key not in ROOT_ENV_KEYS}
    env.update(
        {
            "CLAUDE_PLUGIN_ROOT": str(PROJECT_ROOT),
            "CLAUDE_PROJECT_DIR": str(workspace),
        }
    )
    env.update(values)
    return env


def run_hook(name: str, workspace: Path, payload: dict, **env_values: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOKS / name)],
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        capture_output=True,
        encoding="utf-8",
        env=hook_env(workspace, **env_values),
    )


class GuardRuntimeWriteTest(unittest.TestCase):
    def test_blocks_writes_to_plugin_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = {"tool_input": {"file_path": str(PROJECT_ROOT / "skills" / "novel-creator" / "SKILL.md")}}
            result = run_hook("guard_runtime_write.py", Path(tmp), payload)

            self.assertEqual(result.returncode, 2)
            self.assertIn("插件资产是只读", result.stderr)

    def test_blocks_direct_passport_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            passport = workspace / "novel_output" / "番茄" / "书" / "摘要" / "chapter_001_passport.json"
            payload = {"tool_input": {"file_path": str(passport)}}
            result = run_hook("guard_runtime_write.py", workspace, payload)

            self.assertEqual(result.returncode, 2)
            self.assertIn("写章流水线", result.stderr)

    def test_allows_prose_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            chapter = workspace / "novel_output" / "番茄" / "书" / "正文" / "第001章-开始.md"
            payload = {"tool_input": {"file_path": str(chapter)}}
            result = run_hook("guard_runtime_write.py", workspace, payload)

            self.assertEqual(result.returncode, 0, result.stderr)

    def test_manual_repair_override_allows_state_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            state = workspace / "novel_output" / "番茄" / "书" / "novel_state.json"
            payload = {"tool_input": {"file_path": str(state)}}
            result = run_hook(
                "guard_runtime_write.py",
                workspace,
                payload,
                NOVEL_ALLOW_STATE_WRITE="1",
            )

            self.assertEqual(result.returncode, 0, result.stderr)


class SessionStartTest(unittest.TestCase):
    def test_reports_workspace_and_current_book(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            novel = workspace / "novel_output" / "番茄" / "测试书"
            novel.mkdir(parents=True)
            (novel / "novel_state.json").write_text(
                json.dumps({"title": "测试书", "current_chapter": 3, "last_completed_chapter": 2}, ensure_ascii=False),
                encoding="utf-8",
            )

            result = run_hook("session_start.py", workspace, {"source": "startup"})

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(str(workspace), result.stdout)
            self.assertIn("测试书", result.stdout)
            self.assertIn("第3章", result.stdout)


if __name__ == "__main__":
    unittest.main()
