"""Chapter revision identity: pointer, history, snapshot binding and review gate."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from novel_creation_promax.core.revision_control import (  # noqa: E402
    create_snapshot,
    current_revision,
    ensure_current_revision,
    list_chapter_revisions,
)
from novel_creation_promax.core.review_result import (  # noqa: E402
    chapter_target,
    review_gate,
    save_review_result,
    validate_review_result,
)


def make_novel(tmp: str, chapter: int = 1, text: str = "这是一段正文。\n第二段有冲突。\n") -> Path:
    novel = Path(tmp) / "番茄" / "测试书"
    (novel / "正文").mkdir(parents=True)
    (novel / "摘要").mkdir(parents=True)
    (novel / "素材").mkdir(parents=True)
    chapter_file = novel / "正文" / f"第{chapter:03d}章-测试.md"
    chapter_file.write_text(text * 10, encoding="utf-8")
    return novel


def review_payload(novel: Path, chapter: int = 1, *, target: dict | None = None) -> dict:
    return {
        "schema_version": "1.0",
        "chapter": chapter,
        "mode": "single",
        "target": target if target is not None else chapter_target(novel, chapter),
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


class RevisionIdentityTest(unittest.TestCase):
    def test_creates_version_one_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)

            first = ensure_current_revision(novel, 1, source="test")
            second = ensure_current_revision(novel, 1, source="test")

            self.assertEqual(first["version"], 1)
            self.assertEqual(first["parent_version"], None)
            self.assertEqual(second["revision_id"], first["revision_id"])
            self.assertEqual(current_revision(novel, 1)["revision_id"], first["revision_id"])
            self.assertEqual(len(list_chapter_revisions(novel, 1)), 1)

    def test_content_change_creates_child_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            first = ensure_current_revision(novel, 1, source="writing")

            chapter_file = next((novel / "正文").glob("*.md"))
            chapter_file.write_text(
                chapter_file.read_text(encoding="utf-8") + "\n新增一段。\n",
                encoding="utf-8",
            )
            second = ensure_current_revision(novel, 1, source="revision")

            self.assertEqual(second["version"], 2)
            self.assertEqual(second["parent_version"], 1)
            self.assertEqual(second["parent_revision_id"], first["revision_id"])
            self.assertNotEqual(second["content_hash"], first["content_hash"])
            self.assertEqual([item["version"] for item in list_chapter_revisions(novel, 1)], [1, 2])

    def test_chapter_target_includes_tracked_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            revision = ensure_current_revision(novel, 1, source="test")

            target = chapter_target(novel, 1)

            self.assertEqual(target["revision_state"], "tracked")
            self.assertEqual(target["revision_id"], revision["revision_id"])
            self.assertEqual(target["revision_version"], 1)

    def test_chapter_target_flags_outdated_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            ensure_current_revision(novel, 1, source="test")
            chapter_file = next((novel / "正文").glob("*.md"))
            chapter_file.write_text("外部改动。", encoding="utf-8")

            target = chapter_target(novel, 1)

            self.assertEqual(target["revision_state"], "outdated")
            self.assertEqual(target["revision_id"], "")

    def test_snapshot_binds_to_current_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            revision = ensure_current_revision(novel, 1, source="test")

            manifest = create_snapshot(novel, 1, reason="测试", source="test")

            self.assertEqual(manifest["content_hash"], revision["content_hash"])
            self.assertEqual(manifest["revision_id"], revision["revision_id"])
            self.assertEqual(manifest["revision_version"], 1)


class ReviewRevisionGateTest(unittest.TestCase):
    def test_review_bound_to_current_revision_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            ensure_current_revision(novel, 1, source="test")
            payload = review_payload(novel)

            report = validate_review_result(payload, chapter=1)
            self.assertEqual(report["status"], "pass", report)

            save_review_result(novel, 1, payload)
            self.assertEqual(review_gate(novel, 1)["status"], "pass")

    def test_review_with_unknown_revision_is_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            ensure_current_revision(novel, 1, source="test")
            payload = review_payload(novel)
            payload["target"]["revision_id"] = "rev_20200101T000000_deadbeef"
            payload["target"]["revision_version"] = 99

            save_review_result(novel, 1, payload)
            gate = review_gate(novel, 1)

            self.assertEqual(gate["status"], "stale")
            self.assertTrue(any("revision" in error for error in gate["report"]["errors"]))

    def test_review_without_revision_still_passes_with_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            ensure_current_revision(novel, 1, source="test")
            payload = review_payload(novel)
            payload["target"]["revision_id"] = ""
            payload["target"]["revision_version"] = None

            save_review_result(novel, 1, payload)
            gate = review_gate(novel, 1)

            self.assertEqual(gate["status"], "pass")
            self.assertTrue(any("未绑定 revision_id" in item for item in gate["report"]["warnings"]))

    def test_review_stale_after_new_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            ensure_current_revision(novel, 1, source="test")
            save_review_result(novel, 1, review_payload(novel))

            chapter_file = next((novel / "正文").glob("*.md"))
            chapter_file.write_text("这是完全不同的新正文。", encoding="utf-8")
            ensure_current_revision(novel, 1, source="revision")

            gate = review_gate(novel, 1)

            self.assertEqual(gate["status"], "stale")


if __name__ == "__main__":
    unittest.main()
