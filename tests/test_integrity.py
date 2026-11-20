"""跨产物一致性校验回归测试（stdlib unittest，无需额外依赖）。

运行：
    python3 -m unittest tests.test_integrity -v
"""

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

from novel_creation_promax.core.chapter_commit import commit_id_for, record_chapter_commit  # noqa: E402
from novel_creation_promax.core.integrity import (  # noqa: E402
    report_has_errors,
    verify_novel_integrity,
    verify_root_integrity,
)
from novel_creation_promax.core.jsonio import save_json  # noqa: E402
from novel_creation_promax.core.passport import init_passport, passport_path, save_passport  # noqa: E402
from novel_creation_promax.core.paths import count_chinese_chars  # noqa: E402
from novel_creation_promax.core.review_result import REVIEW_DIMENSIONS, save_review_result  # noqa: E402


def make_novel(tmp: str, name: str = "测试书", platform: str = "番茄") -> Path:
    novel = Path(tmp) / platform / name
    (novel / "正文").mkdir(parents=True)
    (novel / "摘要").mkdir(parents=True)
    (novel / "素材").mkdir(parents=True)
    return novel


def write_chapter(novel: Path, chapter: int = 1, text: str = "") -> Path:
    body = text or ("这是一段正文。" * 50)
    path = novel / "正文" / f"第{chapter:03d}章-测试.md"
    path.write_text(body, encoding="utf-8")
    return path


def write_passport(
    novel: Path,
    chapter: int = 1,
    *,
    chapter_file: Path | None = None,
    pipeline_result: str = "pending",
    **overrides,
) -> dict:
    passport = init_passport(chapter, f"第{chapter}章", chapter_file, novel)
    passport["pipeline_result"] = pipeline_result
    if chapter_file and chapter_file.is_file():
        passport["word_count"] = count_chinese_chars(chapter_file.read_text(encoding="utf-8"))
    else:
        passport["word_count"] = 0
    for key, value in overrides.items():
        if key in {"pipeline", "inputs", "commit", "workflow", "changes"}:
            passport[key].update(value)
        else:
            passport[key] = value
    save_passport(novel, chapter, passport)
    return passport


def write_state(novel: Path, **values) -> None:
    state = {
        "title": novel.name,
        "platform": novel.parent.name,
        "current_chapter": values.pop("current_chapter", 0),
        "last_completed_chapter": values.pop("last_completed_chapter", 0),
        "chapters": values.pop("chapters", {}),
    }
    state.update(values)
    save_json(novel / "novel_state.json", state)


def codes(report: dict, severity: str | None = None) -> list[str]:
    return [
        finding["code"]
        for finding in report["findings"]
        if severity is None or finding["severity"] == severity
    ]


class ChapterPassportIntegrityTest(unittest.TestCase):
    def test_clean_project_has_no_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            chapter_file = write_chapter(novel)
            write_passport(novel, chapter_file=chapter_file)
            write_state(novel, current_chapter=1)

            report = verify_novel_integrity(novel)

            self.assertEqual(report["findings"], [])
            self.assertEqual(report["summary"]["chapters_checked"], 1)

    def test_missing_passport_for_completed_chapter_is_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            write_chapter(novel)
            write_state(
                novel,
                current_chapter=1,
                last_completed_chapter=1,
                chapters={"001": {"audit_status": "pass"}},
            )

            report = verify_novel_integrity(novel)

            self.assertIn("passport_missing", codes(report, "error"))

    def test_orphan_passport_is_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            write_passport(novel, chapter=2, chapter_file=None)
            write_state(novel)

            report = verify_novel_integrity(novel)

            self.assertIn("passport_orphan", codes(report, "warning"))
            self.assertEqual(codes(report, "error"), [])

    def test_passport_pointing_to_missing_chapter_file_is_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            missing = novel / "正文" / "第001章-不存在.md"
            write_passport(novel, chapter=1, chapter_file=missing)
            # 正文目录里放一个别章，确保项目不会被整体跳过
            write_chapter(novel, chapter=9)

            report = verify_novel_integrity(novel)

            self.assertIn("chapter_file_missing", codes(report, "error"))

    def test_word_count_drift_is_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            chapter_file = write_chapter(novel)
            write_passport(novel, chapter_file=chapter_file)
            passport_file = passport_path(novel, 1)
            payload = json.loads(passport_file.read_text(encoding="utf-8"))
            payload["word_count"] = 9999
            save_json(passport_file, payload)

            report = verify_novel_integrity(novel)

            self.assertIn("word_count_drift", codes(report, "warning"))
            self.assertEqual(codes(report, "error"), [])

    def test_missing_declared_input_artifact_is_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            chapter_file = write_chapter(novel)
            write_passport(
                novel,
                chapter_file=chapter_file,
                inputs={"audit_report": "素材/audit_ch001.json"},
            )

            report = verify_novel_integrity(novel)

            self.assertIn("input_missing", codes(report, "warning"))
            self.assertEqual(codes(report, "error"), [])


class CommitIntegrityTest(unittest.TestCase):
    def _commit(self, novel: Path, chapter: int = 1, chapter_file: Path | None = None) -> dict:
        chapter_file = chapter_file or write_chapter(novel, chapter)
        return record_chapter_commit(
            novel,
            chapter,
            chapter_file=chapter_file,
            artifacts={"chapter": chapter_file},
        )

    def _full_commit(self, novel: Path, chapter: int = 1, chapter_file: Path | None = None) -> dict:
        chapter_file = chapter_file or write_chapter(novel, chapter)
        return write_commit(novel, chapter, chapter_file, passport_path(novel, chapter))

    def test_passed_pipeline_without_commit_is_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            chapter_file = write_chapter(novel)
            write_passport(novel, chapter_file=chapter_file, pipeline_result="pass")
            write_state(novel, current_chapter=1, last_completed_chapter=1)

            report = verify_novel_integrity(novel)

            self.assertIn("commit_missing", codes(report, "error"))

    def test_valid_commit_has_no_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            chapter_file = write_chapter(novel)
            commit_id = commit_id_for(1, chapter_file)
            write_passport(
                novel,
                chapter_file=chapter_file,
                pipeline_result="pass",
                commit={
                    "status": "accepted",
                    "path": "素材/commits/chapter_001.commit.json",
                    "id": commit_id,
                },
            )
            commit = self._full_commit(novel, chapter_file=chapter_file)
            self.assertEqual(commit["commit_id"], commit_id)
            write_state(novel, current_chapter=1, last_completed_chapter=1)

            report = verify_novel_integrity(novel)

            self.assertEqual(codes(report, "error"), [])

    def test_tampered_chapter_after_commit_is_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            chapter_file = write_chapter(novel)
            self._commit(novel, chapter_file=chapter_file)
            chapter_file.write_text("被外部改写过的正文。" * 20, encoding="utf-8")

            report = verify_novel_integrity(novel)

            self.assertIn("commit_invalid", codes(report, "error"))

    def test_missing_parent_commit_is_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            chapter_file = write_chapter(novel, chapter=2)
            self._commit(novel, chapter=2, chapter_file=chapter_file)
            write_passport(novel, chapter=2, chapter_file=chapter_file, pipeline_result="pass")
            write_state(novel, current_chapter=2, last_completed_chapter=2)

            report = verify_novel_integrity(novel)

            self.assertIn("commit_parent_gap", codes(report, "warning"))

    def test_existing_commit_but_passport_not_synced_is_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            chapter_file = write_chapter(novel)
            write_passport(novel, chapter_file=chapter_file, pipeline_result="pass")
            self._full_commit(novel, chapter_file=chapter_file)

            report = verify_novel_integrity(novel)

            self.assertIn("passport_commit_unsynced", codes(report, "warning"))
            self.assertEqual(codes(report, "error"), [])


class NovelStateIntegrityTest(unittest.TestCase):
    def test_current_chapter_ahead_of_files_is_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            chapter_file = write_chapter(novel, chapter=1)
            write_passport(novel, chapter=1, chapter_file=chapter_file)
            write_state(novel, current_chapter=5, last_completed_chapter=1)

            report = verify_novel_integrity(novel)

            self.assertIn("state_ahead_of_files", codes(report, "error"))

    def test_state_audit_pass_but_passport_blocked_is_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            chapter_file = write_chapter(novel)
            write_passport(
                novel,
                chapter_file=chapter_file,
                pipeline_result="fail",
                workflow={"stage": "audit", "status": "blocked", "error": "gate failed"},
            )
            write_state(
                novel,
                current_chapter=1,
                chapters={"001": {"audit_status": "pass"}},
            )

            report = verify_novel_integrity(novel)

            self.assertIn("state_passport_conflict", codes(report, "warning"))
            self.assertEqual(codes(report, "error"), [])

    def test_state_passport_reference_missing_is_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            write_state(
                novel,
                current_chapter=0,
                chapters={"001": {"passport": "摘要/chapter_001_passport.json"}},
            )

            report = verify_novel_integrity(novel)

            self.assertIn("state_passport_missing", codes(report, "warning"))


class RootIntegrityTest(unittest.TestCase):
    def test_root_aggregates_projects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            clean = make_novel(str(root), name="干净书")
            clean_file = write_chapter(clean)
            write_passport(clean, chapter_file=clean_file)
            write_state(clean, current_chapter=1)

            broken = make_novel(str(root), name="损坏书")
            write_chapter(broken)
            write_state(broken, current_chapter=1, last_completed_chapter=1)

            report = verify_root_integrity(root)

            self.assertEqual(report["summary"]["projects"], 2)
            self.assertEqual(report["summary"]["errors"], 1)
            self.assertTrue(report_has_errors(report))
            self.assertEqual(len(report["projects"]), 2)
            broken_report = next(item for item in report["projects"] if item["title"] == "损坏书")
            self.assertIn("passport_missing", codes(broken_report, "error"))

    def test_root_skips_workspace_and_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("_workspace", "archive", ".hidden"):
                ignored = root / "番茄" / name
                (ignored / "正文").mkdir(parents=True)
                write_chapter(ignored)
            real = make_novel(str(root), name="真实书")
            real_file = write_chapter(real)
            write_passport(real, chapter_file=real_file)
            write_state(real, current_chapter=1)

            report = verify_root_integrity(root)

            self.assertEqual(report["summary"]["projects"], 1)
            self.assertEqual(report["projects"][0]["title"], "真实书")

    def test_report_has_errors_false_for_warnings_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            write_passport(novel, chapter=2, chapter_file=None)

            report = verify_novel_integrity(novel)

            self.assertEqual(report["summary"]["errors"], 0)
            self.assertFalse(report_has_errors(report))


class ExtraRegressionTest(unittest.TestCase):
    def test_passport_chapter_number_mismatch_is_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            chapter_file = write_chapter(novel)
            write_passport(novel, chapter=1, chapter_file=chapter_file)
            payload = json.loads(passport_path(novel, 1).read_text(encoding="utf-8"))
            payload["chapter"] = 2
            save_json(passport_path(novel, 1), payload)

            report = verify_novel_integrity(novel)

            self.assertIn("passport_chapter_mismatch", codes(report, "error"))

    def test_commit_without_chapter_or_passport_is_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            chapter_file = write_chapter(novel, chapter=3)
            record_chapter_commit(novel, 3, chapter_file=chapter_file, artifacts={"chapter": chapter_file})
            chapter_file.unlink()

            report = verify_novel_integrity(novel)

            self.assertIn("commit_orphan", codes(report, "warning"))

    def test_passport_commit_id_mismatch_is_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            chapter_file = write_chapter(novel)
            commit = record_chapter_commit(
                novel, 1, chapter_file=chapter_file, artifacts={"chapter": chapter_file}
            )
            write_passport(
                novel,
                chapter_file=chapter_file,
                pipeline_result="pass",
                commit={"status": "accepted", "id": "ch001-deadbeefdeadbeef"},
            )

            report = verify_novel_integrity(novel)

            self.assertIn("passport_commit_mismatch", codes(report, "warning"))
            self.assertNotEqual(commit["commit_id"], "ch001-deadbeefdeadbeef")

    def test_state_completed_ahead_of_files_is_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            chapter_file = write_chapter(novel, chapter=1)
            write_passport(novel, chapter=1, chapter_file=chapter_file)
            write_state(novel, current_chapter=1, last_completed_chapter=5)

            report = verify_novel_integrity(novel)

            self.assertIn("state_completed_ahead_of_files", codes(report, "error"))

    def test_state_audit_pass_without_passport_field_is_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            write_state(novel, chapters={"002": {"audit_status": "pass"}})

            report = verify_novel_integrity(novel)

            self.assertIn("state_passport_missing", codes(report, "warning"))


class InputValidationTest(unittest.TestCase):
    def test_missing_novel_dir_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                verify_novel_integrity(Path(tmp) / "不存在的书")

    def test_missing_root_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                verify_root_integrity(Path(tmp) / "不存在的根")


def write_review(novel: Path, chapter: int = 1, *, blocking: bool = False) -> Path:
    issues = []
    if blocking:
        issues = [
            {
                "id": "R-001",
                "severity": "blocker",
                "assessment": "confirmed",
                "dimension": "dialogue",
                "location": "第1段",
                "evidence": "测试阻塞项",
                "impact": "测试阻塞项",
                "repair": "测试阻塞项",
                "source_refs": [],
            }
        ]
    payload = {
        "mode": "single",
        "dimensions": {
            name: {"score": 8, "summary": "ok", "issues": []}
            for name in REVIEW_DIMENSIONS
        },
        "issues": issues,
        "summary": "测试审稿",
    }
    path = save_review_result(novel, chapter, payload, bind_target=True)
    return path


def write_rule_stack(
    novel: Path,
    chapter: int = 1,
    *,
    write_ready: bool = True,
    critical: int = 0,
) -> Path:
    path = novel / "摘要" / f"chapter_{chapter:03d}_rule_stack.json"
    save_json(
        path,
        {
            "chapter": chapter,
            "write_ready": write_ready,
            "unknown_facts": [
                {"id": f"u{index}", "critical": True, "detail": "测试未知事实"}
                for index in range(critical)
            ],
        },
    )
    return path


def write_commit(
    novel: Path,
    chapter: int,
    chapter_file: Path,
    passport_file: Path,
    *,
    include_truth_delta: bool = True,
) -> dict:
    audit = novel / "素材" / f"audit_ch{chapter:03d}.json"
    audit.write_text("{}\n", encoding="utf-8")
    truth_delta = novel / "摘要" / f"chapter_{chapter:03d}_truth_delta.json"
    truth_delta.write_text("{}\n", encoding="utf-8")
    artifacts = {"chapter": chapter_file, "passport": passport_file, "audit": audit}
    if include_truth_delta:
        artifacts["truth_delta"] = truth_delta
    review = novel / "摘要" / f"chapter_{chapter:03d}_review.json"
    if review.is_file():
        artifacts["review_result"] = review
    return record_chapter_commit(
        novel,
        chapter,
        chapter_file=chapter_file,
        artifacts=artifacts,
    )


class StateContractTest(unittest.TestCase):
    def test_resume_stage_and_action_mismatch_are_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            chapter_file = write_chapter(novel)
            write_passport(
                novel,
                chapter_file=chapter_file,
                workflow={"stage": "audit", "status": "running", "next_action": "post --phase audit"},
            )
            write_state(
                novel,
                current_chapter=1,
                resume_point={"chapter": 1, "stage": "commit", "action": "pre", "status": "running"},
            )

            report = verify_novel_integrity(novel)

            self.assertIn("resume_stage_mismatch", codes(report, "error"))
            self.assertIn("resume_action_mismatch", codes(report, "error"))

    def test_stale_review_committed_is_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            chapter_file = write_chapter(novel)
            passport = write_passport(novel, chapter_file=chapter_file)
            write_review(novel)
            write_commit(novel, 1, chapter_file, passport_path(novel, 1))

            chapter_file.write_text("正文已经改过。" * 80, encoding="utf-8")
            report = verify_novel_integrity(novel)

            self.assertIn("review_stale_committed", codes(report, "error"))

    def test_commit_missing_truth_delta_is_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            chapter_file = write_chapter(novel)
            write_passport(novel, chapter_file=chapter_file)
            write_commit(novel, 1, chapter_file, passport_path(novel, 1), include_truth_delta=False)

            report = verify_novel_integrity(novel)

            self.assertIn("commit_artifact_missing", codes(report, "error"))

    def test_rule_stack_not_ready_with_prose_is_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            chapter_file = write_chapter(novel)
            write_passport(novel, chapter_file=chapter_file)
            write_rule_stack(novel, write_ready=False, critical=1)

            report = verify_novel_integrity(novel)

            self.assertIn("rule_stack_not_ready_with_prose", codes(report, "error"))
            self.assertIn("rule_stack_critical_unknown_with_prose", codes(report, "error"))

    def test_review_missing_but_passport_pass_is_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            chapter_file = write_chapter(novel)
            write_passport(novel, chapter_file=chapter_file, pipeline={"review_result": "pass"})

            report = verify_novel_integrity(novel)

            self.assertIn("review_missing_but_pass", codes(report, "error"))


class CliTest(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "tools" / "verify_project_integrity.py"), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def test_cli_reports_errors_with_exit_code_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            write_chapter(novel)
            write_state(novel, current_chapter=1, last_completed_chapter=1)

            result = self._run("--novel-dir", str(novel), "--json")

            self.assertEqual(result.returncode, 1, result.stderr)
            payload = json.loads(result.stdout)
            self.assertIn("passport_missing", [item["code"] for item in payload["findings"]])

    def test_cli_strict_turns_warnings_into_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            write_passport(novel, chapter=2, chapter_file=None)

            relaxed = self._run("--novel-dir", str(novel), "--json")
            strict = self._run("--novel-dir", str(novel), "--json", "--strict")

            self.assertEqual(relaxed.returncode, 0, relaxed.stderr)
            self.assertEqual(strict.returncode, 1, strict.stderr)


if __name__ == "__main__":
    unittest.main()
