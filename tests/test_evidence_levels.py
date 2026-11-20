"""Evidence levels: compile rule_stack, block assumed facts, surface policy."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PROJECT_ROOT / "novel_creation_promax" / "scripts"
for path in (PROJECT_ROOT, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from novel_creation_promax.core.jsonio import save_json  # noqa: E402
from novel_creation_promax.scripts.pre_write_check import check_evidence_levels  # noqa: E402
from story_truth_manager import compile_rule_stack  # noqa: E402

WRITING_GATE = PROJECT_ROOT / "novel_creation_promax" / "scripts" / "writing_gate.py"


def make_novel(root: Path, *, open_question: bool = False) -> Path:
    novel = root / "番茄" / "书"
    for name in ("正文", "摘要", "素材", "设定"):
        (novel / name).mkdir(parents=True, exist_ok=True)
    truth = novel / "设定" / "真相文件"
    truth.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0",
        "records": [
            {
                "id": "char_001",
                "name": "张三",
                "status": "known",
                "role": "主角",
                "motivation": "查清父亲旧案",
                "speech_style": "短句，少解释",
                "behavior_rules": "不主动示弱",
                "reality_anchor": {"income": "月薪 8000", "home": "城西合租"},
            }
        ],
        "open_questions": [],
    }
    if open_question:
        payload["open_questions"] = [
            {
                "entity_id": "char_001",
                "field": "motivation",
                "reason": "作者尚未确定他为什么隐瞒身份",
                "critical": True,
            }
        ]
    (truth / "characters.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    (novel / "novel_state.json").write_text(
        json.dumps(
            {"title": "书", "platform": "番茄", "genre": "现言", "current_chapter": 1},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return novel


def compile_stack(novel: Path) -> dict:
    stack = compile_rule_stack(novel, 1, "第1章")
    save_json(novel / "摘要" / "chapter_001_rule_stack.json", stack)
    return stack


class EvidenceLevelTest(unittest.TestCase):
    def test_clean_project_is_confirmed_and_write_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(Path(tmp))
            stack = compile_stack(novel)

            self.assertTrue(stack["write_ready"])
            self.assertEqual(stack["assumed_facts"], [])
            self.assertEqual(stack["evidence_policy"]["levels"], ["confirmed", "inferred", "assumed"])
            self.assertTrue(stack["active_rules"])
            self.assertTrue(
                all(item.get("evidence_level") == "confirmed" for item in stack["active_rules"])
            )

    def test_critical_open_question_becomes_assumed_and_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(Path(tmp), open_question=True)
            stack = compile_stack(novel)

            self.assertFalse(stack["write_ready"])
            self.assertEqual(len(stack["assumed_facts"]), 1)
            self.assertEqual(stack["assumed_facts"][0]["evidence_level"], "assumed")
            self.assertTrue(any("assumed" in item for item in stack["must_check_before_writing"]))

    def test_pre_write_check_blocks_assumed(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(Path(tmp), open_question=True)
            compile_stack(novel)

            result = check_evidence_levels(str(novel), 1)

            self.assertFalse(result["pass"])
            self.assertEqual(result["status"], "fail")
            self.assertEqual(len(result["assumed_critical"]), 1)

    def test_writing_gate_blocks_when_rule_stack_not_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(Path(tmp), open_question=True)
            compile_stack(novel)
            chapter = novel / "正文" / "第001章-测试.md"
            chapter.write_text("正文。" * 100, encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(WRITING_GATE),
                    "--chapter",
                    str(chapter),
                    "--novel-dir",
                    str(novel),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("rule_stack 就绪", result.stdout)
            self.assertIn("assumed", result.stdout)


if __name__ == "__main__":
    unittest.main()
