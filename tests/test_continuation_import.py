"""拆文续写导入流程测试。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PROJECT_ROOT / "novel_creation_promax" / "scripts"
IMPORT = SCRIPTS / "continuation_import.py"
BOOTSTRAP = SCRIPTS / "project_bootstrap_pipeline.py"
TRUTH = SCRIPTS / "story_truth_manager.py"

ROOT_ENV_KEYS = (
    "CLAUDE_PLUGIN_ROOT",
    "CLAUDE_PROJECT_DIR",
    "NOVEL_PLUGIN_ROOT",
    "NOVEL_WORKSPACE_ROOT",
)

SAMPLE = """第1章 雨夜

沈砚推开旧书店的门，雨水顺着伞骨滴在木地板上。柜台后面，林晚抬起头，手里还捏着一本账册。

“你来晚了。”林晚说。

沈砚笑了笑：“路上有人跟着。”

第2章 账册

第二天清晨，沈砚又来到书店。林晚把账册推到他面前，指着最后一页的墨迹。

“这笔钱不对。”她说，“有人改过。”

沈砚皱眉。他知道林晚从不说没把握的话。

第3章 旧友

周启在茶馆等他们。沈砚和林晚坐下时，周启已经把茶倒好。

“你们在查的那件事，”周启压低声音，“最好停手。”

林晚看了沈砚一眼。沈砚没有回答。
"""


def env_for(workspace: Path) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if key not in ROOT_ENV_KEYS}
    env.update(
        {
            "CLAUDE_PLUGIN_ROOT": str(PROJECT_ROOT),
            "NOVEL_WORKSPACE_ROOT": str(workspace),
            "CLAUDE_PROJECT_DIR": str(workspace),
            "PYTHONIOENCODING": "utf-8",
        }
    )
    return env


def run(command: list[str], workspace: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env_for(workspace),
    )


class ContinuationImportTest(unittest.TestCase):
    def prepare(self, tmp: str) -> tuple[Path, Path, Path]:
        workspace = Path(tmp) / "ws"
        workspace.mkdir()
        source = Path(tmp) / "sample.txt"
        source.write_text(SAMPLE, encoding="utf-8")
        book = workspace / "novel_output" / "番茄" / "续写测试书"
        return workspace, source, book

    def import_project(self, workspace: Path, source: Path, *extra: str) -> subprocess.CompletedProcess:
        return run(
            [
                sys.executable,
                str(IMPORT),
                "--input",
                str(source),
                "--title",
                "续写测试书",
                "--platform",
                "番茄",
                "--genre",
                "悬疑",
                "--confirm-workspace",
                *extra,
            ],
            workspace,
        )

    def test_import_creates_project_and_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace, source, book = self.prepare(tmp)
            result = self.import_project(workspace, source)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            state = json.loads((book / "novel_state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["import_mode"], "continuation")
            self.assertFalse(state["workflow_gate"]["can_write_chapter"])

            report = json.loads(
                (book / "素材" / "continuation_import_report.json").read_text(encoding="utf-8")
            )
            self.assertEqual(report["mode"], "continuation_import")
            self.assertGreaterEqual(report["source"]["chapters"], 3)
            self.assertGreaterEqual(report["source"]["characters"], 3)

            for relative in (
                "设定/人物档案.md",
                "设定/地点档案.md",
                "设定/势力档案.md",
                "设定/事件档案.md",
                "设定/关系网络.md",
                "设定/常识约束.md",
                "细纲/续写细纲.md",
                "记忆/style_dna_baseline.json",
            ):
                self.assertTrue((book / relative).is_file(), relative)
            self.assertFalse(list((book / "细纲").glob("卷*.md")))

            truth = run(
                [sys.executable, str(TRUTH), "validate", "--novel-dir", str(book), "--continuation"],
                workspace,
            )
            self.assertEqual(truth.returncode, 0, truth.stdout + truth.stderr)

    def test_gate_approve_unlocks_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace, source, book = self.prepare(tmp)
            imported = self.import_project(workspace, source)
            self.assertEqual(imported.returncode, 0, imported.stdout + imported.stderr)

            gate = run(
                [
                    sys.executable,
                    str(BOOTSTRAP),
                    "continuation-gate",
                    "--novel-dir",
                    str(book),
                    "--approve",
                ],
                workspace,
            )
            self.assertEqual(gate.returncode, 0, gate.stdout + gate.stderr)

            state = json.loads((book / "novel_state.json").read_text(encoding="utf-8"))
            self.assertTrue(state["workflow_gate"]["can_write_chapter"])
            self.assertEqual(state["workflow_gate"]["bootstrap_status"], "continuation_import")
            self.assertTrue((book / "素材" / "continuation_import_gate.json").is_file())

            workflow = json.loads((book / "摘要" / "workflow.json").read_text(encoding="utf-8"))
            self.assertEqual(workflow["stage"], "write")
            self.assertTrue(workflow["overrides"])

            sys.path.insert(0, str(PROJECT_ROOT))
            from novel_creation_promax.core.gate import verify_bootstrap_gate

            ok, detail = verify_bootstrap_gate(book)
            self.assertTrue(ok, detail)

    def test_first_continuation_chapter_skips_prev_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace, source, book = self.prepare(tmp)
            imported = self.import_project(workspace, source)
            self.assertEqual(imported.returncode, 0, imported.stdout + imported.stderr)

            state = json.loads((book / "novel_state.json").read_text(encoding="utf-8"))
            last = state["import_last_chapter"]
            self.assertEqual(last, 3)

            sys.path.insert(0, str(SCRIPTS))
            import write_pipeline as wp

            self.assertTrue(wp.ensure_prev_chapter_audited(book, last + 1))
            self.assertFalse(wp.ensure_prev_chapter_audited(book, last + 2))

    def test_import_refuses_unconfirmed_empty_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace, source, _book = self.prepare(tmp)
            result = run(
                [
                    sys.executable,
                    str(IMPORT),
                    "--input",
                    str(source),
                    "--title",
                    "未确认书",
                    "--platform",
                    "番茄",
                ],
                workspace,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("尚未确认", result.stderr)
            self.assertFalse((workspace / "novel_output" / "番茄" / "未确认书").exists())

    def test_gate_without_approve_does_not_unlock(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace, source, book = self.prepare(tmp)
            imported = self.import_project(workspace, source)
            self.assertEqual(imported.returncode, 0, imported.stdout + imported.stderr)

            gate = run(
                [
                    sys.executable,
                    str(BOOTSTRAP),
                    "continuation-gate",
                    "--novel-dir",
                    str(book),
                ],
                workspace,
            )
            self.assertEqual(gate.returncode, 0, gate.stdout + gate.stderr)
            state = json.loads((book / "novel_state.json").read_text(encoding="utf-8"))
            self.assertFalse(state["workflow_gate"]["can_write_chapter"])
            self.assertFalse((book / "素材" / "continuation_import_gate.json").exists())


if __name__ == "__main__":
    unittest.main()
