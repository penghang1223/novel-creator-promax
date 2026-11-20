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

    def test_allows_editing_plugin_source_when_roots_match(self):
        """Source repository: plugin_root == workspace_root, editing source is the task."""
        payload = {"tool_input": {"file_path": str(PROJECT_ROOT / "skills" / "novel-creator" / "SKILL.md")}}
        result = run_hook("guard_runtime_write.py", PROJECT_ROOT, payload)

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_source_repo_still_blocks_pipeline_state(self):
        """Source-repo mode must keep protecting pipeline state files."""
        state = PROJECT_ROOT / "novel_output" / "番茄" / "书" / "摘要" / "chapter_001_passport.json"
        payload = {"tool_input": {"file_path": str(state)}}
        result = run_hook("guard_runtime_write.py", PROJECT_ROOT, payload)

        self.assertEqual(result.returncode, 2)
        self.assertIn("写章流水线", result.stderr)

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

    def test_blocks_direct_derived_tracking_view_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            view = workspace / "novel_output" / "番茄" / "书" / "追踪" / "时间线" / "读者已知.md"
            payload = {"tool_input": {"file_path": str(view)}}
            result = run_hook("guard_runtime_write.py", workspace, payload)

            self.assertEqual(result.returncode, 2)
            self.assertIn("写章流水线", result.stderr)

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


class GuardOutlineBeforeProseTest(unittest.TestCase):
    def make_book(self, workspace: Path) -> Path:
        book = workspace / "novel_output" / "番茄" / "测试书"
        (book / "正文").mkdir(parents=True)
        (book / "细纲").mkdir(parents=True)
        return book

    def test_blocks_new_prose_without_outline(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            book = self.make_book(workspace)
            chapter = book / "正文" / "第001章-开始.md"
            payload = {"tool_input": {"file_path": str(chapter)}}

            result = run_hook("guard_outline_before_prose.py", workspace, payload)

            self.assertEqual(result.returncode, 2)
            self.assertIn("缺少细纲", result.stderr)

    def test_allows_new_prose_with_outline(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            book = self.make_book(workspace)
            (book / "细纲" / "细纲_第001章.md").write_text("# 第1章细纲\n", encoding="utf-8")
            chapter = book / "正文" / "第001章-开始.md"
            payload = {"tool_input": {"file_path": str(chapter)}}

            result = run_hook("guard_outline_before_prose.py", workspace, payload)

            self.assertEqual(result.returncode, 0, result.stderr)

    def test_allows_editing_existing_prose(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            book = self.make_book(workspace)
            chapter = book / "正文" / "第001章-开始.md"
            chapter.write_text("旧正文", encoding="utf-8")
            payload = {"tool_input": {"file_path": str(chapter)}}

            result = run_hook("guard_outline_before_prose.py", workspace, payload)

            self.assertEqual(result.returncode, 0, result.stderr)

    def test_allows_non_prose_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            book = self.make_book(workspace)
            note = book / "素材" / "note.md"
            payload = {"tool_input": {"file_path": str(note)}}

            result = run_hook("guard_outline_before_prose.py", workspace, payload)

            self.assertEqual(result.returncode, 0, result.stderr)

    def test_pipeline_override_allows_missing_outline(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            book = self.make_book(workspace)
            chapter = book / "正文" / "第001章-开始.md"
            payload = {"tool_input": {"file_path": str(chapter)}}

            result = run_hook(
                "guard_outline_before_prose.py",
                workspace,
                payload,
                NOVEL_PIPELINE_ACTIVE="1",
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
            self.assertIn("行为红线", result.stdout)


if __name__ == "__main__":
    unittest.main()
