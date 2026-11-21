"""工作区输出位置确认协议测试。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_TOOL = PROJECT_ROOT / "tools" / "workspace.py"
WORKFLOW_TOOL = PROJECT_ROOT / "tools" / "workflow.py"
BOOTSTRAP_SCRIPT = PROJECT_ROOT / "novel_creation_promax" / "scripts" / "project_bootstrap_pipeline.py"
SESSION_HOOK = PROJECT_ROOT / "hooks" / "session_start.py"

ROOT_ENV_KEYS = (
    "CLAUDE_PLUGIN_ROOT",
    "CLAUDE_PROJECT_DIR",
    "NOVEL_PLUGIN_ROOT",
    "NOVEL_WORKSPACE_ROOT",
)


def clean_env(workspace: Path, plugin: Path = PROJECT_ROOT) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if key not in ROOT_ENV_KEYS}
    env.update({"CLAUDE_PLUGIN_ROOT": str(plugin), "CLAUDE_PROJECT_DIR": str(workspace)})
    return env


def run_tool(tool: Path, workspace: Path, *args: str, plugin: Path = PROJECT_ROOT) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(tool), "--workspace", str(workspace), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=clean_env(workspace, plugin),
    )


def run_script(script: Path, workspace: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=clean_env(workspace),
    )


def write_marker(workspace: Path, *, path_value: str | None = None, confirmed: bool = True) -> None:
    payload = {
        "schema_version": "1.0",
        "confirmed": confirmed,
        "workspace": path_value if path_value is not None else str(workspace.resolve()),
        "confirmed_at": "2026-11-21T00:00:00",
        "confirmed_by": "test",
    }
    (workspace / ".novel-workspace.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def add_book(workspace: Path, name: str = "书") -> Path:
    book = workspace / "novel_output" / "番茄" / name
    book.mkdir(parents=True, exist_ok=True)
    (book / "novel_state.json").write_text(
        json.dumps({"title": name, "platform": "番茄"}, ensure_ascii=False), encoding="utf-8"
    )
    return book


class StatusTest(unittest.TestCase):
    def test_missing_marker_is_unconfirmed(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            result = run_tool(WORKSPACE_TOOL, workspace, "status", "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["confirmed"])
            self.assertEqual(payload["reason"], "missing")
            self.assertEqual(payload["legacy_books"], 0)

    def test_valid_marker_is_confirmed(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            write_marker(workspace)
            payload = json.loads(run_tool(WORKSPACE_TOOL, workspace, "status", "--json").stdout)
            self.assertTrue(payload["confirmed"])
            self.assertEqual(payload["reason"], "ok")

    def test_path_mismatch_invalidates_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            write_marker(workspace, path_value="/somewhere/else")
            payload = json.loads(run_tool(WORKSPACE_TOOL, workspace, "status", "--json").stdout)
            self.assertFalse(payload["confirmed"])
            self.assertEqual(payload["reason"], "path_mismatch")

    def test_invalid_marker_is_unconfirmed(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / ".novel-workspace.json").write_text("{not json", encoding="utf-8")
            payload = json.loads(run_tool(WORKSPACE_TOOL, workspace, "status", "--json").stdout)
            self.assertFalse(payload["confirmed"])
            self.assertEqual(payload["reason"], "invalid")

    def test_legacy_books_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            add_book(workspace)
            payload = json.loads(run_tool(WORKSPACE_TOOL, workspace, "status", "--json").stdout)
            self.assertFalse(payload["confirmed"])
            self.assertEqual(payload["legacy_books"], 1)


class ConfirmTest(unittest.TestCase):
    def test_confirm_writes_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            result = run_tool(WORKSPACE_TOOL, workspace, "confirm")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads((workspace / ".novel-workspace.json").read_text(encoding="utf-8"))
            self.assertTrue(payload["confirmed"])
            self.assertEqual(payload["confirmed_by"], "user")
            self.assertEqual(payload["workspace"], str(workspace.resolve()))

    def test_confirm_legacy_marks_by_legacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            add_book(workspace)
            result = run_tool(WORKSPACE_TOOL, workspace, "confirm", "--legacy")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads((workspace / ".novel-workspace.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["confirmed_by"], "legacy")

    def test_plugin_root_is_blocked(self):
        result = run_tool(WORKSPACE_TOOL, PROJECT_ROOT, "status", "--json")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["dangerous"], "plugin_root")
        self.assertFalse(payload["confirmed"])

        confirm = run_tool(WORKSPACE_TOOL, PROJECT_ROOT, "confirm")
        self.assertEqual(confirm.returncode, 2)
        self.assertFalse((PROJECT_ROOT / ".novel-workspace.json").exists())

    def test_forget_removes_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            write_marker(workspace)
            result = run_tool(WORKSPACE_TOOL, workspace, "forget", "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(result.stdout)["removed"])
            self.assertFalse((workspace / ".novel-workspace.json").exists())


class EntryPointGateTest(unittest.TestCase):
    def test_workflow_start_refuses_unconfirmed(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            result = run_tool(WORKFLOW_TOOL, workspace, "start", "--platform", "番茄", "--genre", "都市")
            self.assertEqual(result.returncode, 2)
            self.assertIn("尚未确认", result.stderr)
            self.assertFalse((workspace / "novel_output" / "_workspace" / "workflow.json").exists())

    def test_workflow_start_confirm_flag_writes_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            result = run_tool(
                WORKFLOW_TOOL,
                workspace,
                "start",
                "--platform",
                "番茄",
                "--genre",
                "都市",
                "--confirm-workspace",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            marker = json.loads((workspace / ".novel-workspace.json").read_text(encoding="utf-8"))
            self.assertEqual(marker["confirmed_by"], "cli")

    def test_workflow_start_auto_confirms_legacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            add_book(workspace)
            result = run_tool(WORKFLOW_TOOL, workspace, "start", "--platform", "番茄", "--genre", "都市")
            self.assertEqual(result.returncode, 0, result.stderr)
            marker = json.loads((workspace / ".novel-workspace.json").read_text(encoding="utf-8"))
            self.assertEqual(marker["confirmed_by"], "legacy")

    def test_init_refuses_unconfirmed(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            result = run_script(
                BOOTSTRAP_SCRIPT,
                workspace,
                "init",
                "--platform",
                "番茄",
                "--title",
                "确认测试书",
                "--genre",
                "都市",
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("尚未确认", result.stderr)
            self.assertFalse((workspace / "novel_output").exists())

    def test_init_confirm_flag_proceeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            result = run_script(
                BOOTSTRAP_SCRIPT,
                workspace,
                "init",
                "--platform",
                "番茄",
                "--title",
                "确认测试书",
                "--genre",
                "都市",
                "--confirm-workspace",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((workspace / "MEMORY.md").is_file())
            marker = json.loads((workspace / ".novel-workspace.json").read_text(encoding="utf-8"))
            self.assertEqual(marker["confirmed_by"], "cli")


class SessionHookTest(unittest.TestCase):
    def run_hook(self, workspace: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SESSION_HOOK)],
            input=json.dumps({"source": "startup"}),
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=clean_env(workspace),
        )

    def test_unconfirmed_workspace_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_hook(Path(tmp))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("未确认", result.stdout)
            self.assertIn("首次创作前需确认产物保存位置", result.stdout)

    def test_confirmed_workspace_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            write_marker(workspace)
            result = self.run_hook(workspace)
            self.assertIn("已确认", result.stdout)

    def test_legacy_workspace_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            add_book(workspace)
            result = self.run_hook(workspace)
            self.assertIn("存量书", result.stdout)

    def test_plugin_root_is_reported(self):
        result = self.run_hook(PROJECT_ROOT)
        self.assertIn("插件资产根", result.stdout)


if __name__ == "__main__":
    unittest.main()
