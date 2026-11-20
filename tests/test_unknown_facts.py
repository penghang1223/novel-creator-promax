"""Unknown-fact blockers: truth files -> rule_stack -> pre_write_check."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "novel_creation_promax" / "scripts"
for entry in (PROJECT_ROOT, SCRIPTS_DIR):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from novel_creation_promax.core.jsonio import save_json  # noqa: E402
from story_truth_manager import (  # noqa: E402
    compile_rule_stack,
    collect_unknown_facts,
    write_truth_brief,
)
import pre_write_check  # noqa: E402


def make_novel(tmp: str) -> Path:
    novel = Path(tmp) / "番茄" / "测试书"
    for name in ("正文", "摘要", "素材", "设定/真相文件"):
        (novel / name).mkdir(parents=True)
    save_json(
        novel / "novel_state.json",
        {"schema_version": "2.0", "title": "测试书", "word_count_range": [2800, 3200]},
    )
    return novel


def write_characters(novel: Path, *, open_questions: list, records: list | None = None) -> None:
    save_json(
        novel / "设定" / "真相文件" / "characters.json",
        {
            "schema_version": "1.0",
            "kind": "characters",
            "records": records or [],
            "open_questions": open_questions,
        },
    )


def high_score_answers() -> dict[str, str]:
    return {
        str(index): "这是一个足够长的答案，说明本章的具体安排、冲突推进和结尾悬念。"
        for index in range(1, 10)
    }


class CollectUnknownFactsTest(unittest.TestCase):
    def test_open_question_is_critical_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            write_characters(
                novel,
                open_questions=[
                    {"entity_id": "char_001", "field": "motivation", "reason": "作者尚未确定"}
                ],
            )

            facts = collect_unknown_facts(novel, 1)

            self.assertEqual(len(facts), 1)
            self.assertTrue(facts[0]["critical"])
            self.assertEqual(facts[0]["field"], "motivation")

    def test_warning_open_question_does_not_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            write_characters(
                novel,
                open_questions=[
                    {"entity_id": "char_001", "field": "hobby", "reason": "可选", "critical": False}
                ],
            )

            stack = compile_rule_stack(novel, 1, "第1章 测试")

            self.assertEqual(len(stack["unknown_facts"]), 1)
            self.assertEqual(stack["blockers"], [])
            self.assertTrue(stack["write_ready"])

    def test_chapter_scoped_question_only_applies_to_that_chapter(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            write_characters(
                novel,
                open_questions=[
                    {"entity_id": "char_001", "field": "motivation", "reason": "第2章才确定", "chapters": [2]}
                ],
            )

            self.assertEqual(collect_unknown_facts(novel, 1), [])
            self.assertEqual(len(collect_unknown_facts(novel, 2)), 1)

    def test_chapter_scoped_question_accepts_single_integer(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            write_characters(
                novel,
                open_questions=[
                    {"entity_id": "char_001", "field": "motivation", "reason": "第12章才确定", "chapters": 12}
                ],
            )

            self.assertEqual(collect_unknown_facts(novel, 1), [])
            self.assertEqual(len(collect_unknown_facts(novel, 12)), 1)

    def test_record_status_unknown_is_collected(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            write_characters(
                novel,
                open_questions=[],
                records=[
                    {"id": "char_001", "name": "林砚", "status": "unknown", "unknown_reason": "身份未定"}
                ],
            )

            facts = collect_unknown_facts(novel, 1)

            self.assertEqual(len(facts), 1)
            self.assertEqual(facts[0]["source"], "record_status")
            self.assertTrue(facts[0]["critical"])


class RuleStackTest(unittest.TestCase):
    def test_critical_unknown_blocks_write_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            write_characters(
                novel,
                open_questions=[
                    {"entity_id": "char_001", "field": "motivation", "reason": "作者尚未确定"}
                ],
            )

            stack = compile_rule_stack(novel, 1, "第1章 测试")

            self.assertFalse(stack["write_ready"])
            self.assertEqual(len(stack["blockers"]), 1)
            self.assertTrue(any("critical" in item for item in stack["must_check_before_writing"]))

    def test_truth_brief_lists_unknown_facts(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            write_characters(
                novel,
                open_questions=[
                    {"entity_id": "char_001", "field": "motivation", "reason": "作者尚未确定"}
                ],
            )
            stack = compile_rule_stack(novel, 1, "第1章 测试")
            brief = Path(tmp) / "brief.md"

            write_truth_brief(stack, brief)

            text = brief.read_text(encoding="utf-8")
            self.assertIn("未知事实", text)
            self.assertIn("CRITICAL", text)
            self.assertIn("作者尚未确定", text)


class PreWriteCheckTest(unittest.TestCase):
    def _write_rule_stack(self, novel: Path, facts: list[dict]) -> None:
        save_json(
            novel / "摘要" / "chapter_001_rule_stack.json",
            {"chapter": 1, "unknown_facts": facts, "blockers": [f for f in facts if f.get("critical")]},
        )

    def test_critical_unknown_blocks_pre_write_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            self._write_rule_stack(
                novel,
                [
                    {
                        "file": "characters.json",
                        "entity_id": "char_001",
                        "field": "motivation",
                        "reason": "作者尚未确定",
                        "critical": True,
                    }
                ],
            )

            report = pre_write_check.run_pre_write_check(
                str(novel), 1, title="第1章 测试", answers=high_score_answers()
            )

            self.assertGreaterEqual(report["score"], 70)
            self.assertFalse(report["pass"])
            self.assertEqual(len(report["blockers"]), 1)
            self.assertTrue(any("critical 未知事实" in warning for warning in report["warnings"]))

    def test_warning_unknown_does_not_block_pre_write_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            self._write_rule_stack(
                novel,
                [
                    {
                        "file": "characters.json",
                        "entity_id": "char_001",
                        "field": "hobby",
                        "reason": "可选",
                        "critical": False,
                    }
                ],
            )

            report = pre_write_check.run_pre_write_check(
                str(novel), 1, title="第1章 测试", answers=high_score_answers()
            )

            self.assertTrue(report["pass"])
            self.assertEqual(report["blockers"], [])
            self.assertEqual(len(report["unknown_facts"]), 1)

    def test_missing_rule_stack_warns_but_does_not_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)

            report = pre_write_check.run_pre_write_check(
                str(novel), 1, title="第1章 测试", answers=high_score_answers()
            )

            self.assertTrue(report["pass"])
            self.assertTrue(any("未找到 rule_stack" in warning for warning in report["warnings"]))


if __name__ == "__main__":
    unittest.main()
