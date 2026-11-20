"""Review basis: rule stack, truth brief, taskbook and memory pack binding."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from novel_creation_promax.core.jsonio import save_json  # noqa: E402
from novel_creation_promax.core.review_basis import (  # noqa: E402
    build_review_basis,
    review_basis_gate,
)
from novel_creation_promax.core.review_result import (  # noqa: E402
    chapter_target,
    review_gate,
    save_review_result,
)
from novel_creation_promax.core.revision_control import ensure_current_revision  # noqa: E402


def make_novel(tmp: str) -> Path:
    novel = Path(tmp) / "番茄" / "测试书"
    for name in ("正文", "摘要", "素材", "设定/真相文件"):
        (novel / name).mkdir(parents=True)
    (novel / "正文" / "第001章-测试.md").write_text(
        "这是一段正文。\n第二段有冲突。\n" * 5, encoding="utf-8"
    )
    save_json(
        novel / "摘要" / "chapter_001_rule_stack.json",
        {"schema_version": "1.0", "chapter": 1, "active_rules": [{"id": "r1"}]},
    )
    (novel / "素材" / "chapter_001_truth_brief.md").write_text(
        "# 第001章 真相约束简报\n", encoding="utf-8"
    )
    (novel / "摘要" / "chapter_001_taskbook.md").write_text(
        "# 第1章写作任务书\n", encoding="utf-8"
    )
    save_json(novel / "摘要" / "chapter_001_pack.json", {"chapter": 1, "characters": []})
    save_json(
        novel / "设定" / "真相文件" / "characters.json",
        {"schema_version": "1.0", "kind": "characters", "records": []},
    )
    ensure_current_revision(novel, 1, source="test")
    return novel


def review_payload(novel: Path) -> dict:
    bundle = build_review_basis(novel, 1)
    return {
        "schema_version": "1.0",
        "chapter": 1,
        "mode": "single",
        "target": chapter_target(novel, 1),
        "basis": bundle["basis"],
        "expected_versions": bundle["expected_versions"],
        "dimensions": {
            name: {"score": 8, "summary": "正常", "issues": []}
            for name in ("dialogue", "coolpoint", "structure", "anti_ai", "reading_power")
        },
        "issues": [],
        "blocking_count": 0,
        "status": "pass",
        "grade": "A",
        "summary": "测试审稿",
    }


class BuildBasisTest(unittest.TestCase):
    def test_basis_includes_review_inputs_and_excludes_raw_truth(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)

            bundle = build_review_basis(novel, 1)
            refs = {item["resource_type"]: item for item in bundle["basis"]["source_refs"]}

            self.assertEqual(set(refs), {"chapter", "rule_stack", "truth_brief", "taskbook", "memory_pack"})
            self.assertTrue(refs["chapter"]["required"])
            self.assertTrue(refs["rule_stack"]["required"])
            self.assertTrue(refs["taskbook"]["exists"])
            self.assertEqual(len(bundle["basis"]["input_fingerprint"]), 64)
            self.assertIn("rule_stack:001", bundle["expected_versions"])
            self.assertNotIn("truth_file:characters.json", bundle["expected_versions"])

    def test_basis_changes_when_rule_stack_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            first = build_review_basis(novel, 1)

            save_json(
                novel / "摘要" / "chapter_001_rule_stack.json",
                {"schema_version": "1.0", "chapter": 1, "active_rules": [{"id": "r2"}]},
            )
            second = build_review_basis(novel, 1)

            self.assertNotEqual(
                first["basis"]["input_fingerprint"], second["basis"]["input_fingerprint"]
            )


class BasisGateTest(unittest.TestCase):
    def test_unchanged_inputs_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            payload = review_payload(novel)

            result = review_basis_gate(novel, 1, payload)

            self.assertEqual(result["status"], "pass", result)

    def test_rule_stack_change_makes_basis_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            payload = review_payload(novel)
            save_json(
                novel / "摘要" / "chapter_001_rule_stack.json",
                {"schema_version": "1.0", "chapter": 1, "active_rules": [{"id": "changed"}]},
            )

            result = review_basis_gate(novel, 1, payload)

            self.assertEqual(result["status"], "stale")
            self.assertTrue(any("rule_stack" in error for error in result["errors"]))

    def test_taskbook_change_makes_basis_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            payload = review_payload(novel)
            (novel / "摘要" / "chapter_001_taskbook.md").write_text(
                "# 第1章写作任务书（已修改）\n", encoding="utf-8"
            )

            result = review_basis_gate(novel, 1, payload)

            self.assertEqual(result["status"], "stale")
            self.assertTrue(any("taskbook" in error for error in result["errors"]))

    def test_raw_truth_file_change_does_not_invalidate_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            payload = review_payload(novel)
            # post:truth writes truth files after the review; this must not stale it.
            save_json(
                novel / "设定" / "真相文件" / "characters.json",
                {"schema_version": "1.0", "kind": "characters", "records": [{"id": "char_001"}]},
            )

            result = review_basis_gate(novel, 1, payload)

            self.assertEqual(result["status"], "pass", result)

    def test_expected_versions_mismatch_is_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            payload = review_payload(novel)
            payload["expected_versions"]["rule_stack:001"] = "0" * 64

            result = review_basis_gate(novel, 1, payload)

            self.assertEqual(result["status"], "stale")

    def test_missing_basis_only_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)

            result = review_basis_gate(novel, 1, {"chapter": 1})

            self.assertEqual(result["status"], "pass")
            self.assertTrue(any("未绑定 basis" in warning for warning in result["warnings"]))

    def test_review_gate_blocks_stale_basis(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            save_review_result(novel, 1, review_payload(novel))
            self.assertEqual(review_gate(novel, 1)["status"], "pass")

            save_json(
                novel / "摘要" / "chapter_001_rule_stack.json",
                {"schema_version": "1.0", "chapter": 1, "active_rules": [{"id": "changed"}]},
            )

            gate = review_gate(novel, 1)

            self.assertEqual(gate["status"], "stale")
            self.assertTrue(any("rule_stack" in error for error in gate["report"]["errors"]))


if __name__ == "__main__":
    unittest.main()
