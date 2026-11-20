"""Structured review result contract, target binding and gate tests."""

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

from novel_creation_promax.core.review_result import (  # noqa: E402
    chapter_target,
    init_review_result,
    load_review_result,
    normalize_review_result,
    render_review_markdown,
    review_gate,
    review_path,
    save_review_result,
    validate_review_result,
)


def make_novel(tmp: str, chapter: int = 1, text: str = "这是一段正文。\n第二段有冲突。\n") -> Path:
    novel = Path(tmp) / "番茄" / "测试书"
    (novel / "正文").mkdir(parents=True)
    (novel / "摘要").mkdir(parents=True)
    chapter_file = novel / "正文" / f"第{chapter:03d}章-测试.md"
    chapter_file.write_text(text * 10, encoding="utf-8")
    return novel


def fake_target(chapter: int = 1) -> dict:
    return {
        "chapter_file": f"正文/第{chapter:03d}章-测试.md",
        "sha256": "a" * 64,
        "word_count": 100,
    }


def dimensions(score: int = 8) -> dict:
    return {
        name: {"score": score, "summary": f"{name} 正常", "issues": []}
        for name in ("dialogue", "coolpoint", "structure", "anti_ai", "reading_power")
    }


def review_payload(
    *,
    chapter: int = 1,
    blockers: int = 0,
    majors: int = 0,
    target: dict | None = None,
    quote: str = "这是一段正文。",
) -> dict:
    issues = []
    for index in range(blockers):
        issues.append(
            {
                "id": f"R-B{index + 1:02d}",
                "severity": "blocker",
                "assessment": "issue",
                "dimension": "structure",
                "location": f"第{index + 1}段",
                "evidence": "正文证据",
                "impact": "会破坏连续性",
                "repair": "补写过渡并重跑审稿",
                "source_refs": [{"quote": quote}],
            }
        )
    for index in range(majors):
        issues.append(
            {
                "id": f"R-M{index + 1:02d}",
                "severity": "major",
                "assessment": "issue",
                "dimension": "anti_ai",
                "location": "第2段",
                "evidence": "他感到一阵愤怒。",
                "impact": "情绪标签化",
                "repair": "改成动作暗示",
                "source_refs": [{"quote": quote}],
            }
        )
    blocking = sum(1 for item in issues if item["severity"] == "blocker")
    return {
        "schema_version": "1.0",
        "chapter": chapter,
        "mode": "single",
        "target": target if target is not None else fake_target(chapter),
        "dimensions": dimensions(),
        "issues": issues,
        "blocking_count": blocking,
        "status": "blocked" if blocking else "pass",
        "grade": "",
        "summary": "测试用审稿结果",
        "generated_at": "2026-11-20T12:00:00",
    }


class NormalizeTest(unittest.TestCase):
    def test_derives_blocking_status_and_grade(self):
        normalized = normalize_review_result(review_payload(blockers=1), chapter=1)

        self.assertEqual(normalized["blocking_count"], 1)
        self.assertEqual(normalized["status"], "blocked")
        self.assertEqual(normalized["grade"], "A")
        self.assertEqual(normalized["issues"][0]["severity"], "blocker")
        self.assertEqual(normalized["issues"][0]["source_refs"][0]["quote"], "这是一段正文。")

    def test_recomputes_stale_counts_instead_of_trusting_them(self):
        payload = review_payload(blockers=2)
        payload["blocking_count"] = 0
        payload["status"] = "pass"

        normalized = normalize_review_result(payload, chapter=1)

        self.assertEqual(normalized["blocking_count"], 2)
        self.assertEqual(normalized["status"], "blocked")

    def test_init_template_is_blocked_and_marked_unavailable(self):
        template = init_review_result(3, target=fake_target(3))
        normalized = normalize_review_result(template, chapter=3)

        self.assertEqual(normalized["chapter"], 3)
        self.assertEqual(normalized["status"], "blocked")
        self.assertEqual(normalized["target"]["sha256"], "a" * 64)
        self.assertEqual(normalized["issues"][0]["assessment"], "unavailable")
        self.assertGreaterEqual(normalized["blocking_count"], 1)


class ValidateTest(unittest.TestCase):
    def test_valid_payload_passes(self):
        report = validate_review_result(review_payload(blockers=1), chapter=1)
        self.assertEqual(report["status"], "pass", report)

    def test_missing_target_fails(self):
        payload = review_payload()
        del payload["target"]

        report = validate_review_result(payload, chapter=1)

        self.assertEqual(report["status"], "fail")
        self.assertTrue(any("target" in error for error in report["errors"]))

    def test_bad_target_hash_fails(self):
        payload = review_payload()
        payload["target"]["sha256"] = "not-a-hash"

        report = validate_review_result(payload, chapter=1)

        self.assertEqual(report["status"], "fail")
        self.assertTrue(any("SHA-256" in error for error in report["errors"]))

    def test_missing_dimension_fails(self):
        payload = review_payload()
        del payload["dimensions"]["reading_power"]

        report = validate_review_result(payload, chapter=1)

        self.assertEqual(report["status"], "fail")
        self.assertTrue(any("reading_power" in error for error in report["errors"]))

    def test_blocker_without_repair_fails(self):
        payload = review_payload(blockers=1)
        payload["issues"][0]["repair"] = ""

        report = validate_review_result(payload, chapter=1)

        self.assertEqual(report["status"], "fail")
        self.assertTrue(any("repair" in error for error in report["errors"]))

    def test_blocker_without_source_refs_fails(self):
        payload = review_payload(blockers=1)
        payload["issues"][0]["source_refs"] = []

        report = validate_review_result(payload, chapter=1)

        self.assertEqual(report["status"], "fail")
        self.assertTrue(any("source_refs" in error for error in report["errors"]))

    def test_unavailable_blocker_does_not_require_source_refs(self):
        payload = review_payload(blockers=1)
        payload["issues"][0]["assessment"] = "unavailable"
        payload["issues"][0]["source_refs"] = []

        report = validate_review_result(payload, chapter=1)

        self.assertEqual(report["status"], "pass", report)

    def test_invalid_issue_code_fails(self):
        payload = review_payload(blockers=1)
        payload["issues"][0]["code"] = "bad code"

        report = validate_review_result(payload, chapter=1)

        self.assertEqual(report["status"], "fail")
        self.assertTrue(any("code" in error for error in report["errors"]))

    def test_issue_code_is_normalized(self):
        payload = review_payload(blockers=1)
        payload["issues"][0]["code"] = "pov_leak"

        normalized = normalize_review_result(payload, chapter=1)

        self.assertEqual(normalized["issues"][0]["code"], "POV_LEAK")

    def test_status_mismatch_fails(self):
        payload = review_payload(blockers=1)
        payload["status"] = "pass"

        report = validate_review_result(payload, chapter=1)

        self.assertEqual(report["status"], "fail")
        self.assertTrue(any("status" in error for error in report["errors"]))

    def test_unknown_severity_fails(self):
        payload = review_payload()
        payload["issues"] = [
            {
                "id": "R-001",
                "severity": "fatal",
                "dimension": "logic",
                "evidence": "x",
                "source_refs": [],
            }
        ]
        payload["blocking_count"] = 0
        payload["status"] = "pass"

        report = validate_review_result(payload, chapter=1)

        self.assertEqual(report["status"], "fail")
        self.assertGreaterEqual(len(report["errors"]), 2)


class GateTest(unittest.TestCase):
    def test_missing_is_reported_as_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            gate = review_gate(Path(tmp), 1)
            self.assertEqual(gate["status"], "missing")
            self.assertEqual(gate["blocking_count"], 0)

    def test_save_and_load_roundtrip_with_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            target = chapter_target(novel, 1)
            path = save_review_result(novel, 1, review_payload(target=target))

            self.assertEqual(path, review_path(novel, 1))
            loaded = load_review_result(novel, 1)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded["target"]["sha256"], target["sha256"])
            self.assertEqual(review_gate(novel, 1)["status"], "pass")

    def test_blocked_gate_exposes_blockers(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp, chapter=2)
            save_review_result(
                novel,
                2,
                review_payload(chapter=2, blockers=1, target=chapter_target(novel, 2)),
            )

            gate = review_gate(novel, 2)

            self.assertEqual(gate["status"], "blocked")
            self.assertEqual(gate["blocking_count"], 1)
            self.assertEqual(gate["issues"][0]["severity"], "blocker")

    def test_stale_when_chapter_changes_after_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            save_review_result(novel, 1, review_payload(target=chapter_target(novel, 1)))

            chapter_file = next((novel / "正文").glob("*.md"))
            chapter_file.write_text(
                chapter_file.read_text(encoding="utf-8") + "\n作者又改了一段。\n",
                encoding="utf-8",
            )

            gate = review_gate(novel, 1)

            self.assertEqual(gate["status"], "stale")
            self.assertTrue(any("过期" in error for error in gate["report"]["errors"]))

    def test_quote_not_in_chapter_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            save_review_result(
                novel,
                1,
                review_payload(
                    blockers=1,
                    target=chapter_target(novel, 1),
                    quote="这句话在正文里并不存在。",
                ),
            )

            gate = review_gate(novel, 1)

            self.assertEqual(gate["status"], "invalid")
            self.assertTrue(any("引文未在正文中找到" in error for error in gate["report"]["errors"]))

    def test_save_bind_target_fills_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            payload = review_payload()
            del payload["target"]

            save_review_result(novel, 1, payload, bind_target=True)

            loaded = load_review_result(novel, 1)
            self.assertEqual(loaded["target"]["sha256"], chapter_target(novel, 1)["sha256"])
            self.assertEqual(review_gate(novel, 1)["status"], "pass")

    def test_invalid_json_is_invalid_not_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            payload = review_payload(target=chapter_target(novel, 1))
            payload["blocking_count"] = 99
            review_path(novel, 1).write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )

            gate = review_gate(novel, 1)

            self.assertEqual(gate["status"], "invalid")


class OffsetAndDuplicateKeyTest(unittest.TestCase):
    def _payload_with_ref(self, novel: Path, ref: dict) -> dict:
        payload = review_payload(majors=1, target=chapter_target(novel, 1))
        payload["issues"][0]["source_refs"] = [ref]
        return payload

    def test_exact_character_offset_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            chapter_file = next((novel / "正文").glob("*.md"))
            text = chapter_file.read_text(encoding="utf-8")
            start = text.index("第二段")
            ref = {"quote": "第二段", "start": start, "end": start + len("第二段")}

            save_review_result(novel, 1, self._payload_with_ref(novel, ref))

            self.assertEqual(review_gate(novel, 1)["status"], "pass")

    def test_start_only_uses_quote_length(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            chapter_file = next((novel / "正文").glob("*.md"))
            text = chapter_file.read_text(encoding="utf-8")
            ref = {"quote": "第二段", "start": text.index("第二段")}

            save_review_result(novel, 1, self._payload_with_ref(novel, ref))

            self.assertEqual(review_gate(novel, 1)["status"], "pass")

    def test_wrong_character_offset_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            ref = {"quote": "第二段", "start": 0, "end": len("第二段")}

            save_review_result(novel, 1, self._payload_with_ref(novel, ref))
            gate = review_gate(novel, 1)

            self.assertEqual(gate["status"], "invalid")
            self.assertTrue(any("引文未在正文中找到" in error for error in gate["report"]["errors"]))

    def test_end_without_start_fails_schema(self):
        payload = review_payload(majors=1)
        payload["issues"][0]["source_refs"] = [{"quote": "第二段", "end": 3}]

        report = validate_review_result(payload, chapter=1)

        self.assertEqual(report["status"], "fail")
        self.assertTrue(any("end 必须与 start" in error for error in report["errors"]))

    def test_duplicate_json_key_makes_gate_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            payload = review_payload(target=chapter_target(novel, 1))
            raw = json.dumps(payload, ensure_ascii=False, indent=2)
            raw = raw.replace('"chapter": 1,', '"chapter": 1,\n  "chapter": 1,', 1)
            review_path(novel, 1).write_text(raw, encoding="utf-8")

            gate = review_gate(novel, 1)

            self.assertEqual(gate["status"], "invalid")
            self.assertTrue(any("重复字段" in error for error in gate["report"]["errors"]))

    def test_cli_validate_rejects_duplicate_json_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            payload = review_payload(target=chapter_target(novel, 1))
            raw = json.dumps(payload, ensure_ascii=False, indent=2)
            raw = raw.replace('"chapter": 1,', '"chapter": 1,\n  "chapter": 1,', 1)
            path = Path(tmp) / "duplicate.json"
            path.write_text(raw, encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "tools" / "review_result.py"),
                    "validate",
                    "--novel-dir",
                    str(novel),
                    "--chapter",
                    "1",
                    "--input",
                    str(path),
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("重复字段", result.stderr)


class RenderTest(unittest.TestCase):
    def test_markdown_contains_target_scores_and_blocking_issues(self):
        markdown = render_review_markdown(
            review_payload(blockers=1, majors=1), chapter=1
        )

        self.assertIn("第1章 审稿报告", markdown)
        self.assertIn("审稿目标", markdown)
        self.assertIn("对话质感", markdown)
        self.assertIn("Blocking（必须修复）", markdown)
        self.assertIn("Major（建议修复）", markdown)
        self.assertIn("原文", markdown)
        self.assertIn("补写过渡并重跑审稿", markdown)

    def test_markdown_without_issues_says_deliverable(self):
        markdown = render_review_markdown(review_payload(), chapter=1)
        self.assertIn("无 blocking issue", markdown)


class CliTest(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "tools" / "review_result.py"), *args],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_init_target_status_save_render_and_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            novel_arg = str(novel)

            target = self.run_cli("target", "--novel-dir", novel_arg, "--chapter", "1", "--json")
            self.assertEqual(target.returncode, 0, target.stdout + target.stderr)
            target_payload = json.loads(target.stdout)
            self.assertEqual(len(target_payload["sha256"]), 64)

            init = self.run_cli("init", "--novel-dir", novel_arg, "--chapter", "1")
            self.assertEqual(init.returncode, 0, init.stdout + init.stderr)
            template = load_review_result(novel, 1)
            self.assertEqual(template["target"]["sha256"], target_payload["sha256"])

            validate = self.run_cli("validate", "--novel-dir", novel_arg, "--chapter", "1")
            self.assertEqual(validate.returncode, 0, validate.stdout + validate.stderr)

            status = self.run_cli("status", "--novel-dir", novel_arg, "--chapter", "1")
            self.assertEqual(status.returncode, 1, status.stdout + status.stderr)
            self.assertIn("blocked", status.stdout)

            pass_file = Path(tmp) / "review_pass.json"
            pass_file.write_text(
                json.dumps(review_payload(), ensure_ascii=False), encoding="utf-8"
            )
            save = self.run_cli(
                "save", "--novel-dir", novel_arg, "--chapter", "1",
                "--input", str(pass_file), "--bind-target",
            )
            self.assertEqual(save.returncode, 0, save.stdout + save.stderr)

            status = self.run_cli("status", "--novel-dir", novel_arg, "--chapter", "1")
            self.assertEqual(status.returncode, 0, status.stdout + status.stderr)

            output = Path(tmp) / "report.md"
            render = self.run_cli(
                "render", "--novel-dir", novel_arg, "--chapter", "1",
                "--output", str(output),
            )
            self.assertEqual(render.returncode, 0, render.stdout + render.stderr)
            self.assertIn("审稿目标", output.read_text(encoding="utf-8"))

            chapter_file = next((novel / "正文").glob("*.md"))
            chapter_file.write_text(
                chapter_file.read_text(encoding="utf-8") + "\n新增内容。\n",
                encoding="utf-8",
            )
            stale = self.run_cli("status", "--novel-dir", novel_arg, "--chapter", "1")
            self.assertEqual(stale.returncode, 1, stale.stdout + stale.stderr)
            self.assertIn("stale", stale.stdout)

    def test_save_rejects_missing_target_without_bind(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            payload = review_payload()
            del payload["target"]
            payload_file = Path(tmp) / "review.json"
            payload_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            result = self.run_cli(
                "save", "--novel-dir", str(novel), "--chapter", "1",
                "--input", str(payload_file),
            )

            self.assertEqual(result.returncode, 1)
            self.assertFalse(review_path(novel, 1).exists())


if __name__ == "__main__":
    unittest.main()
