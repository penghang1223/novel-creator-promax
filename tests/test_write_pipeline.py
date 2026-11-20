"""write_pipeline 状态机与门禁回归测试（stdlib unittest）。

只覆盖确定性控制流；真正的外部脚本（真相文件校验、审计脚本）用
mock 隔离，避免测试依赖子进程和完整项目资料。
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "novel_creation_promax" / "scripts"
for entry in (PROJECT_ROOT, SCRIPTS_DIR):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import write_pipeline as wp  # noqa: E402

from novel_creation_promax.core.chapter_commit import commit_path  # noqa: E402
from novel_creation_promax.core.jsonio import load_json, save_json  # noqa: E402
from novel_creation_promax.core.passport import init_passport, passport_path, save_passport  # noqa: E402


def make_project(tmp: str, *, gate: bool = True) -> Path:
    novel = Path(tmp) / "番茄" / "测试书"
    for name in ("正文", "摘要", "素材"):
        (novel / name).mkdir(parents=True)
    if gate:
        save_json(
            novel / "素材" / "project_bootstrap_gate.json",
            {"status": "pass", "can_write_chapter": True},
        )
    save_json(
        novel / "novel_state.json",
        {
            "schema_version": "2.0",
            "title": "测试书",
            "platform": "番茄",
            "current_chapter": 0,
            "last_completed_chapter": 0,
            "chapters": {},
            "workflow_gate": {
                "can_write_chapter": gate,
                "bootstrap_report": "素材/project_bootstrap_gate.json",
            },
        },
    )
    return novel


def write_chapter(novel: Path, chapter: int = 1) -> Path:
    path = novel / "正文" / f"第{chapter:03d}章-测试.md"
    path.write_text("这是一段正文。" * 60, encoding="utf-8")
    return path


def write_passport(novel: Path, chapter: int, chapter_file: Path | None, **pipeline) -> dict:
    passport = init_passport(chapter, f"第{chapter}章", chapter_file, novel)
    passport["pipeline"].update(pipeline)
    if chapter_file:
        passport["chapter_file"] = chapter_file.relative_to(novel).as_posix()
        passport["word_count"] = 360
    save_passport(novel, chapter, passport)
    return passport


def commit_args(novel: Path, chapter: int = 1) -> argparse.Namespace:
    return argparse.Namespace(
        novel_dir=str(novel),
        chapter=chapter,
        title=f"第{chapter}章",
        memory_dir="",
        answers_file="",
        scene_plan="",
        quality_mode="",
        quality_review_report="",
        phase="commit",
        override_prev_audit=False,
        override_reason="",
    )


class WorkflowCheckpointTest(unittest.TestCase):
    def test_checkpoint_updates_passport_and_novel_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_project(tmp)
            passport = init_passport(1, "第1章", None, novel)

            workflow = wp.save_workflow_checkpoint(
                novel,
                1,
                passport,
                stage="pre",
                status="pass",
                next_action="write_then_post",
            )

            saved = load_json(passport_path(novel, 1), {})
            state = load_json(novel / "novel_state.json", {})
            self.assertEqual(workflow["stage"], "pre")
            self.assertEqual(workflow["status"], "pass")
            self.assertEqual(saved["workflow"]["stage"], "pre")
            self.assertEqual(saved["workflow"]["attempts"]["pre"], 1)
            self.assertEqual(state["chapters"]["001"]["workflow"]["stage"], "pre")
            self.assertEqual(state["resume_point"]["chapter"], 1)


class PreviousChapterGateTest(unittest.TestCase):
    def test_blocks_when_previous_chapter_has_no_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_project(tmp)
            write_chapter(novel, 1)
            write_passport(novel, 1, novel / "正文" / "第001章-测试.md")

            self.assertFalse(
                wp.ensure_prev_chapter_audited(novel, 2, stage="pre")
            )

    def test_allows_when_previous_passport_audit_passed(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_project(tmp)
            chapter_file = write_chapter(novel, 1)
            passport = write_passport(
                novel,
                1,
                chapter_file,
                post_write_audit="pass",
            )
            passport["pipeline_result"] = "pass"
            save_passport(novel, 1, passport)

            self.assertTrue(
                wp.ensure_prev_chapter_audited(novel, 2, stage="pre")
            )

    def test_override_requires_reason_and_records_debt(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_project(tmp)
            write_chapter(novel, 1)

            denied = wp.ensure_prev_chapter_audited(
                novel, 2, allow_override=True, override_reason=""
            )
            self.assertFalse(denied)
            self.assertEqual(load_json(novel / "novel_state.json", {}).get("override_debt"), None)

            allowed = wp.ensure_prev_chapter_audited(
                novel, 2, allow_override=True, override_reason="历史章节补写"
            )
            self.assertTrue(allowed)
            debts = load_json(novel / "novel_state.json", {}).get("override_debt", [])
            self.assertEqual(len(debts), 1)
            self.assertEqual(debts[0]["reason"], "历史章节补写")
            self.assertFalse(debts[0]["resolved"])


class CommitPhaseTest(unittest.TestCase):
    def test_blocks_and_marks_passport_when_required_phase_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_project(tmp)
            chapter_file = write_chapter(novel)
            write_passport(
                novel,
                1,
                chapter_file,
                writing_gate="pass",
                post_write_audit="fail",
                normalizer="pass",
                truth_delta="pending",
                truth_sync="pending",
            )

            with mock.patch.object(wp, "ensure_truth_files", return_value=True):
                ok = wp.post_commit_phase(commit_args(novel))

            self.assertFalse(ok)
            self.assertFalse(commit_path(novel, 1).exists())
            passport = load_json(passport_path(novel, 1), {})
            self.assertEqual(passport["commit"]["status"], "blocked")
            self.assertEqual(passport["pipeline_result"], "fail")
            self.assertEqual(passport["workflow"]["stage"], "commit")
            self.assertEqual(passport["workflow"]["status"], "blocked")

    def test_accepts_and_writes_commit_when_all_required_phases_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_project(tmp)
            chapter_file = write_chapter(novel)
            audit_file = novel / "素材" / "audit_ch001.json"
            save_json(audit_file, {"chapter": 1, "status": "pass"})
            save_json(novel / "摘要" / "chapter_001_truth_delta.json", {"chapter": 1})
            save_json(novel / "素材" / "truth_delta_ch001.json", {"chapter": 1, "status": "pass"})
            save_json(novel / "素材" / "truth_apply_ch001.json", {"chapter": 1, "status": "pass"})
            passport = write_passport(
                novel,
                1,
                chapter_file,
                writing_gate="pass",
                post_write_audit="pass",
                normalizer="pass",
                truth_delta="pass",
                truth_sync="pass",
            )
            passport["inputs"]["audit_report"] = "素材/audit_ch001.json"
            save_passport(novel, 1, passport)

            with mock.patch.object(wp, "ensure_truth_files", return_value=True):
                ok = wp.post_commit_phase(commit_args(novel))

            self.assertTrue(ok)
            self.assertTrue(commit_path(novel, 1).exists())
            passport = load_json(passport_path(novel, 1), {})
            self.assertEqual(passport["commit"]["status"], "accepted")
            self.assertEqual(passport["pipeline_result"], "pass")
            self.assertTrue(passport["commit"]["id"])
            state = load_json(novel / "novel_state.json", {})
            self.assertEqual(state["last_completed_chapter"], 1)
            self.assertEqual(state["chapters"]["001"]["audit_status"], "pass")


if __name__ == "__main__":
    unittest.main()
