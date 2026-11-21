"""工作流阶段门禁测试。"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOL = PROJECT_ROOT / "tools" / "workflow.py"


def run(workspace: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOL), "--workspace", str(workspace), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def make_workspace(tmp: str) -> Path:
    workspace = Path(tmp)
    (workspace / "素材" / "调研").mkdir(parents=True)
    (workspace / "创意").mkdir(parents=True)
    (workspace / "novel_output" / "番茄" / "书").mkdir(parents=True)
    write_json(
        workspace / ".novel-workspace.json",
        {
            "schema_version": "1.0",
            "confirmed": True,
            "workspace": str(workspace.resolve()),
            "confirmed_at": "2026-11-21T00:00:00",
            "confirmed_by": "test",
        },
    )
    return workspace


def add_research(workspace: Path) -> Path:
    path = workspace / "素材" / "调研" / "2026-11-20_番茄_热门方向.md"
    path.write_text("# 调研\n\n有效内容", encoding="utf-8")
    return path


def add_idea(workspace: Path) -> Path:
    path = workspace / "创意" / "创意卡_2026-11-20.md"
    path.write_text("# 创意卡\n\n有效内容", encoding="utf-8")
    return path


def add_sealed_project(workspace: Path) -> Path:
    novel = workspace / "novel_output" / "番茄" / "书"
    write_json(
        novel / "novel_state.json",
        {"title": "书", "platform": "番茄", "workflow_gate": {"can_write_chapter": True}},
    )
    return novel


def add_commit(workspace: Path) -> None:
    novel = workspace / "novel_output" / "番茄" / "书"
    write_json(
        novel / "素材" / "commits" / "chapter_001.commit.json",
        {"chapter": 1, "status": "accepted", "commit_id": "ch001-x"},
    )


def add_publish_state(workspace: Path) -> None:
    novel = workspace / "novel_output" / "番茄" / "书"
    state = json.loads((novel / "novel_state.json").read_text(encoding="utf-8"))
    state["publish_state"] = {"番茄": {"status": "synced"}}
    write_json(novel / "novel_state.json", state)


class WorkflowTest(unittest.TestCase):
    def test_start_awaits_research(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = make_workspace(tmp)
            result = run(workspace, "start", "--platform", "番茄", "--genre", "都市")
            self.assertEqual(result.returncode, 0, result.stderr)

            status = run(workspace, "status", "--json")
            payload = json.loads(status.stdout)
            self.assertEqual(payload["stage"], "")
            self.assertEqual(payload["next"], "research")

    def test_advance_requires_stage_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = make_workspace(tmp)
            run(workspace, "start", "--platform", "番茄", "--genre", "都市")

            no_report = run(workspace, "advance", "--to", "research")
            self.assertEqual(no_report.returncode, 1)
            self.assertIn("调研", no_report.stderr + no_report.stdout)

            add_research(workspace)
            research_done = run(workspace, "advance", "--to", "research")
            self.assertEqual(research_done.returncode, 0, research_done.stderr)

            no_idea = run(workspace, "advance", "--to", "idea")
            self.assertEqual(no_idea.returncode, 1)

            add_idea(workspace)
            idea_done = run(workspace, "advance", "--to", "idea")
            self.assertEqual(idea_done.returncode, 0, idea_done.stderr)

    def test_advance_to_init_requires_seal(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = make_workspace(tmp)
            run(workspace, "start", "--platform", "番茄", "--genre", "都市")
            add_research(workspace)
            run(workspace, "advance", "--to", "research")
            add_idea(workspace)
            run(workspace, "advance", "--to", "idea")

            unsealed = run(workspace, "advance", "--to", "init", "--novel-dir", "novel_output/番茄/书")
            self.assertEqual(unsealed.returncode, 1)

            add_sealed_project(workspace)
            sealed = run(workspace, "advance", "--to", "init", "--novel-dir", "novel_output/番茄/书")
            self.assertEqual(sealed.returncode, 0, sealed.stderr)

    def test_advance_to_write_and_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = make_workspace(tmp)
            run(workspace, "start", "--platform", "番茄", "--genre", "都市")
            add_research(workspace)
            run(workspace, "advance", "--to", "research")
            add_idea(workspace)
            run(workspace, "advance", "--to", "idea")
            add_sealed_project(workspace)
            run(workspace, "advance", "--to", "init", "--novel-dir", "novel_output/番茄/书")

            no_commit = run(workspace, "advance", "--to", "write", "--novel-dir", "novel_output/番茄/书")
            self.assertEqual(no_commit.returncode, 1)

            add_commit(workspace)
            written = run(workspace, "advance", "--to", "write", "--novel-dir", "novel_output/番茄/书")
            self.assertEqual(written.returncode, 0, written.stderr)

            no_publish = run(workspace, "advance", "--to", "publish", "--novel-dir", "novel_output/番茄/书")
            self.assertEqual(no_publish.returncode, 1)

            add_publish_state(workspace)
            published = run(workspace, "advance", "--to", "publish", "--novel-dir", "novel_output/番茄/书")
            self.assertEqual(published.returncode, 0, published.stderr)

    def test_force_records_override_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = make_workspace(tmp)
            run(workspace, "start", "--platform", "番茄", "--genre", "都市")

            forced = run(
                workspace,
                "advance",
                "--to",
                "init",
                "--novel-dir",
                "novel_output/番茄/书",
                "--force",
                "--reason",
                "已有立项资料",
            )
            self.assertEqual(forced.returncode, 0, forced.stderr)

            state = json.loads((workspace / "novel_output" / "_workspace" / "workflow.json").read_text(encoding="utf-8"))
            self.assertEqual(state["stage"], "init")
            self.assertTrue(state["overrides"])
            self.assertEqual(state["overrides"][0]["reason"], "已有立项资料")

    def test_gate_does_not_mutate_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = make_workspace(tmp)
            run(workspace, "start", "--platform", "番茄", "--genre", "都市")

            gate = run(workspace, "gate", "--to", "research")
            self.assertEqual(gate.returncode, 1)
            state = json.loads((workspace / "novel_output" / "_workspace" / "workflow.json").read_text(encoding="utf-8"))
            self.assertEqual(state["stage"], "")


def add_book(workspace: Path, name: str = "书一", platform: str = "番茄") -> Path:
    novel = workspace / "novel_output" / platform / name
    novel.mkdir(parents=True, exist_ok=True)
    write_json(
        novel / "novel_state.json",
        {"title": name, "platform": platform, "current_chapter": 0},
    )
    return novel


class PerNovelWorkflowTest(unittest.TestCase):
    def test_each_book_has_independent_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = make_workspace(tmp)
            first = add_book(workspace, "书一")
            second = add_book(workspace, "书二")

            self.assertEqual(
                run(workspace, "start", "--platform", "番茄", "--genre", "都市", "--novel-dir", str(first)).returncode,
                0,
            )
            self.assertEqual(
                run(workspace, "start", "--platform", "番茄", "--genre", "玄幻", "--novel-dir", str(second)).returncode,
                0,
            )
            add_research(workspace)
            advanced = run(workspace, "advance", "--to", "research", "--novel-dir", str(first))
            self.assertEqual(advanced.returncode, 0, advanced.stderr)

            first_status = json.loads(run(workspace, "status", "--json", "--novel-dir", str(first)).stdout)
            second_status = json.loads(run(workspace, "status", "--json", "--novel-dir", str(second)).stdout)
            self.assertEqual(first_status["stage"], "research")
            self.assertEqual(second_status["stage"], "")

            overview = json.loads(run(workspace, "status", "--json").stdout)
            self.assertEqual(len(overview["books"]), 2)
            by_title = {item["title"]: item for item in overview["books"]}
            self.assertEqual(by_title["书一"]["stage"], "research")
            self.assertEqual(by_title["书二"]["stage"], "")

    def test_migrate_legacy_global_workflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = make_workspace(tmp)
            book = add_book(workspace, "书一")

            run(workspace, "start", "--platform", "番茄", "--genre", "都市")
            add_research(workspace)
            run(workspace, "advance", "--to", "research", "--novel-dir", str(book))

            migrated = run(workspace, "migrate", "--novel-dir", str(book))
            self.assertEqual(migrated.returncode, 0, migrated.stderr)
            per_novel = json.loads((book / "摘要" / "workflow.json").read_text(encoding="utf-8"))
            self.assertEqual(per_novel["stage"], "research")
            self.assertTrue((workspace / "novel_output" / "_workspace" / "workflow.legacy.json").is_file())

            status = json.loads(run(workspace, "status", "--json", "--novel-dir", str(book)).stdout)
            self.assertEqual(status["stage"], "research")


if __name__ == "__main__":
    unittest.main()
