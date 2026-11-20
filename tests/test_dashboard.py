"""Per-book and workspace dashboards."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from novel_creation_promax.core.dashboard import (  # noqa: E402
    GLOBAL_HEADER_RE,
    NOVEL_HEADER_RE,
    check_dashboards,
    global_dashboard_path,
    novel_dashboard_path,
    write_dashboards,
)

DASHBOARD_TOOL = PROJECT_ROOT / "tools" / "dashboard.py"


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def make_book(
    workspace: Path,
    name: str = "书一",
    stage: str = "write",
    *,
    with_chapter: bool = True,
) -> Path:
    novel = workspace / "novel_output" / "番茄" / name
    (novel / "正文").mkdir(parents=True, exist_ok=True)
    (novel / "摘要").mkdir(parents=True, exist_ok=True)
    (novel / "素材" / "commits").mkdir(parents=True, exist_ok=True)
    (novel / "设定" / "真相文件").mkdir(parents=True, exist_ok=True)
    write_json(
        novel / "novel_state.json",
        {
            "title": name,
            "platform": "番茄",
            "genre": "现言",
            "current_chapter": 1 if with_chapter else 0,
            "last_completed_chapter": 1 if with_chapter else 0,
            "updated_at": "2026-11-20T10:00:00",
            "resume_point": {"action": "pre", "hint": "写下一章"},
        },
    )
    write_json(
        novel / "摘要" / "workflow.json",
        {
            "schema_version": "1.0",
            "book": name,
            "platform": "番茄",
            "genre": "现言",
            "stage": stage,
            "status": "done",
            "created_at": "2026-11-20T09:00:00",
            "updated_at": "2026-11-20T10:00:00",
        },
    )
    write_json(
        novel / "设定" / "真相文件" / "foreshadowing.json",
        {"records": [{"id": "FS-01", "status": "open"}]},
    )
    if with_chapter:
        (novel / "正文" / "第001章-测试.md").write_text("正文。" * 100, encoding="utf-8")
        write_json(
            novel / "摘要" / "chapter_001_passport.json",
            {
                "chapter": 1,
                "word_count": 300,
                "pipeline": {"post_write_audit": "pass", "review_result": "pass"},
                "commit": {"status": "accepted", "id": "ch001-x"},
                "workflow": {"stage": "commit", "status": "pass"},
            },
        )
    return novel


class DashboardTest(unittest.TestCase):
    def test_writes_per_book_and_global_dashboards(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            first = make_book(workspace, "书一", "write")
            second = make_book(workspace, "书二", "init", with_chapter=False)

            write_dashboards(workspace)

            first_text = (first / "看板.md").read_text(encoding="utf-8")
            second_text = (second / "看板.md").read_text(encoding="utf-8")
            global_text = global_dashboard_path(workspace).read_text(encoding="utf-8")

            self.assertRegex(first_text, NOVEL_HEADER_RE)
            self.assertRegex(second_text, NOVEL_HEADER_RE)
            self.assertRegex(global_text, GLOBAL_HEADER_RE)
            self.assertIn("书一", global_text)
            self.assertIn("书二", global_text)
            self.assertIn("未回收伏笔：1 条", first_text)

    def test_check_detects_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            book = make_book(workspace, "书一")
            write_dashboards(workspace)

            self.assertEqual(check_dashboards(workspace), [])

            path = novel_dashboard_path(book)
            path.write_text("手工改过的看板\n", encoding="utf-8")
            problems = check_dashboards(workspace)
            self.assertTrue(any(str(path) in item for item in problems))

    def test_cli_check_and_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            make_book(workspace, "书一")
            write_dashboards(workspace)

            passed = subprocess.run(
                [sys.executable, str(DASHBOARD_TOOL), "--workspace", str(workspace), "--check", "--json"],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(passed.returncode, 0, passed.stdout + passed.stderr)
            payload = json.loads(passed.stdout)
            self.assertTrue(payload["passed"])

            novel_dashboard_path(workspace / "novel_output" / "番茄" / "书一").write_text(
                "漂移\n", encoding="utf-8"
            )
            drifted = subprocess.run(
                [sys.executable, str(DASHBOARD_TOOL), "--workspace", str(workspace), "--check", "--json"],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(drifted.returncode, 1)
            self.assertFalse(json.loads(drifted.stdout)["passed"])


if __name__ == "__main__":
    unittest.main()
