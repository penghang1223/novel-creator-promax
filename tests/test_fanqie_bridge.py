"""番茄发布器桥接层与同步路径测试。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FANQIE = PROJECT_ROOT / "auto_publish" / "fanqie_auto_publish"
SYNC = PROJECT_ROOT / "scripts" / "sync_to_fanqie.py"

ROOT_ENV_KEYS = (
    "CLAUDE_PLUGIN_ROOT",
    "CLAUDE_PROJECT_DIR",
    "NOVEL_PLUGIN_ROOT",
    "NOVEL_WORKSPACE_ROOT",
    "NOVEL_FANQIE_PUBLISHER",
    "NOVEL_SKIP_PLAYWRIGHT_CHECK",
    "FAKE_ENGINE_OUT",
    "HOME",
)

FAKE_ENGINE = """\
import json, os, sys
from pathlib import Path
Path(os.environ["FAKE_ENGINE_OUT"]).write_text(json.dumps({
    "cwd": os.getcwd(),
    "argv": sys.argv[1:],
    "script": sys.argv[0],
}, ensure_ascii=False), encoding="utf-8")
Path("engine_ran.txt").write_text("ok", encoding="utf-8")
"""


def base_env(workspace: Path, home: Path) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if key not in ROOT_ENV_KEYS}
    env.update(
        {
            "CLAUDE_PLUGIN_ROOT": str(PROJECT_ROOT),
            "NOVEL_WORKSPACE_ROOT": str(workspace),
            "HOME": str(home),
            "NOVEL_SKIP_PLAYWRIGHT_CHECK": "1",
        }
    )
    return env


def write_engine(directory: Path, name: str = "publish.py") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(FAKE_ENGINE, encoding="utf-8")
    return path


class PublishBridgeTest(unittest.TestCase):
    def test_runs_engine_in_workspace_publish_dir(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home:
            workspace = Path(tmp)
            engine = write_engine(workspace / "engine")
            output = workspace / "engine_out.json"
            env = base_env(workspace, Path(home))
            env["NOVEL_FANQIE_PUBLISHER"] = str(engine)
            env["FAKE_ENGINE_OUT"] = str(output)

            result = subprocess.run(
                [sys.executable, str(FANQIE / "publish.py"), "--book", "书", "--count", "2", "--draft"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            payload = json.loads(output.read_text(encoding="utf-8"))
            publish_dir = workspace / ".novel_publish" / "fanqie"
            self.assertEqual(Path(payload["cwd"]).resolve(), publish_dir.resolve())
            self.assertEqual(payload["argv"], ["--book", "书", "--count", "2", "--draft"])
            self.assertTrue((publish_dir / "engine_ran.txt").is_file())
            self.assertTrue((publish_dir / "chapters").is_dir())

    def test_copies_login_state_from_engine_dir(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home:
            workspace = Path(tmp)
            engine = write_engine(workspace / "engine")
            (engine.parent / "state.json").write_text('{"cookies": []}', encoding="utf-8")
            env = base_env(workspace, Path(home))
            env["NOVEL_FANQIE_PUBLISHER"] = str(engine.parent)
            env["FAKE_ENGINE_OUT"] = str(workspace / "out.json")

            result = subprocess.run(
                [sys.executable, str(FANQIE / "publish.py"), "--book", "书"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            state = workspace / ".novel_publish" / "fanqie" / "state.json"
            self.assertEqual(state.read_text(encoding="utf-8"), '{"cookies": []}')

    def test_login_bridge_runs_login_engine(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home:
            workspace = Path(tmp)
            engine = write_engine(workspace / "engine", name="login.py")
            output = workspace / "login_out.json"
            env = base_env(workspace, Path(home))
            env["NOVEL_FANQIE_PUBLISHER"] = str(engine)
            env["FAKE_ENGINE_OUT"] = str(output)

            result = subprocess.run(
                [sys.executable, str(FANQIE / "login.py")],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(payload["script"].endswith("login.py"))
            self.assertEqual(
                Path(payload["cwd"]).resolve(),
                (workspace / ".novel_publish" / "fanqie").resolve(),
            )

    def test_missing_engine_exits_with_guidance(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home:
            workspace = Path(tmp)
            env = base_env(workspace, Path(home))
            result = subprocess.run(
                [sys.executable, str(FANQIE / "publish.py"), "--book", "书"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("未找到番茄发布引擎", result.stderr)
            self.assertIn("NOVEL_FANQIE_PUBLISHER", result.stderr)

    def test_check_reports_engine_and_dir(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home:
            workspace = Path(tmp)
            engine = write_engine(workspace / "engine")
            env = base_env(workspace, Path(home))
            env["NOVEL_FANQIE_PUBLISHER"] = str(engine)
            result = subprocess.run(
                [sys.executable, str(FANQIE / "publish.py"), "--check"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("引擎:", result.stdout)
            self.assertIn(".novel_publish", result.stdout)


class SyncPathTest(unittest.TestCase):
    def test_sync_writes_to_workspace_not_plugin(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home:
            workspace = Path(tmp)
            book = workspace / "novel_output" / "番茄" / "测试书"
            (book / "正文").mkdir(parents=True)
            (book / "正文" / "第001章-开始.md").write_text("# 第1章\n\n正文内容。", encoding="utf-8")
            (book / "novel_state.json").write_text(
                json.dumps({"title": "测试书", "platform": "番茄", "chapters": {}}, ensure_ascii=False),
                encoding="utf-8",
            )
            env = base_env(workspace, Path(home))

            result = subprocess.run(
                [sys.executable, str(SYNC), "测试书"],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            target = workspace / ".novel_publish" / "fanqie" / "chapters" / "测试书" / "第001章-开始.txt"
            self.assertTrue(target.is_file())
            self.assertIn("正文内容", target.read_text(encoding="utf-8"))
            self.assertFalse(
                (PROJECT_ROOT / "auto_publish" / "fanqie_auto_publish" / "chapters" / "测试书").exists()
            )


if __name__ == "__main__":
    unittest.main()
