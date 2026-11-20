"""Long-term idea library: archive, split, dedupe, index and search."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import idea_library  # noqa: E402

BATCH = """# 创意卡 · 测试

## 0. 排序表

| 名 | 分 |
|---|---|

## 1. 她只想退休，却被推上凤位

题材：女频
平台：番茄
标签：宫斗, 退休, 反差

一句话 logline：她想退休，却被推上凤位。

总分 88.0 / S / 可进入立项

## 2. 离婚当天，我成了前夫的甲方

题材：女频
平台：番茄
标签：职场, 追妻

一句话 logline：离婚当天，她成了前夫的甲方。

总分 87.0 / S / 可进入立项
"""

RESEARCH = """# 番茄女频热门方向调研

平台：番茄
题材：女频

## 结论摘要

女频现言与职场婚恋仍有空位。
"""


class IdeaLibraryTest(unittest.TestCase):
    def _workspace(self, tmp: str) -> Path:
        workspace = Path(tmp)
        (workspace / "创意").mkdir(parents=True)
        (workspace / "素材" / "调研").mkdir(parents=True)
        (workspace / "创意" / "batch.md").write_text(BATCH, encoding="utf-8")
        (workspace / "素材" / "调研" / "research.md").write_text(RESEARCH, encoding="utf-8")
        return workspace

    def test_init_creates_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self._workspace(tmp)
            result = idea_library.init_library(workspace / "创意库")

            self.assertTrue((workspace / "创意库" / "创意卡").is_dir())
            self.assertTrue((workspace / "创意库" / "调研").is_dir())
            self.assertTrue((workspace / "创意库" / "_INDEX.json").is_file())
            self.assertTrue((workspace / "创意库" / "_INDEX.md").is_file())
            self.assertIn("library", result)

    def test_split_archive_extracts_per_idea_scores_and_tags(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self._workspace(tmp)
            result = idea_library.archive_file(
                workspace,
                workspace / "创意" / "batch.md",
                kind="idea",
                platform="番茄",
                genre="女频",
                split=True,
            )

            self.assertEqual(len(result["results"]), 2)
            index = idea_library.load_index(workspace / "创意库")
            titles = [entry["title"] for entry in index["ideas"]]
            scores = [entry["score"] for entry in index["ideas"]]
            self.assertEqual(titles, ["她只想退休，却被推上凤位", "离婚当天，我成了前夫的甲方"])
            self.assertEqual(scores, [88.0, 87.0])
            self.assertIn("宫斗", index["ideas"][0]["tags"])
            self.assertIn("职场", index["ideas"][1]["tags"])

    def test_duplicate_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self._workspace(tmp)
            first = idea_library.archive_file(
                workspace, workspace / "创意" / "batch.md", kind="idea", split=True
            )
            second = idea_library.archive_file(
                workspace, workspace / "创意" / "batch.md", kind="idea", split=True
            )

            self.assertEqual(len(first["results"]), 2)
            self.assertEqual([item["status"] for item in second["results"]], ["duplicate", "duplicate"])

    def test_search_filters_and_returns_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self._workspace(tmp)
            idea_library.archive_file(
                workspace, workspace / "创意" / "batch.md", kind="idea",
                platform="番茄", genre="女频", split=True,
            )
            idea_library.archive_file(
                workspace, workspace / "素材" / "调研" / "research.md", kind="research",
                platform="番茄", genre="女频",
            )

            by_title = idea_library.search(workspace, "凤位")
            by_tag = idea_library.search(workspace, "", tag="宫斗")
            only_research = idea_library.search(workspace, "", platform="番茄")

            self.assertEqual(by_title[0]["title"], "她只想退休，却被推上凤位")
            self.assertEqual([item["title"] for item in by_tag], ["她只想退休，却被推上凤位"])
            self.assertTrue(any(item["kind"] == "research" for item in only_research))

    def test_rebuild_index_from_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self._workspace(tmp)
            library = workspace / "创意库"
            idea_library.init_library(library)
            manual = library / "创意卡" / "IDEA-20260101-001_手工.md"
            manual.write_text(
                "---\n"
                "id: IDEA-20260101-001\n"
                "title: 手工条目\n"
                "type: idea\n"
                "platform: 起点\n"
                "genre: 玄幻\n"
                "score: 90\n"
                "status: selected\n"
                "---\n\n# 手工条目\n\n正文\n",
                encoding="utf-8",
            )

            result = idea_library.rebuild_index(workspace)

            self.assertEqual(result["ideas"], 1)
            index = idea_library.load_index(library)
            self.assertEqual(index["ideas"][0]["id"], "IDEA-20260101-001")
            self.assertEqual(index["ideas"][0]["score"], 90.0)

    def test_library_dir_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self._workspace(tmp)
            custom = workspace / "my-ideas"
            idea_library.archive_file(
                workspace, workspace / "创意" / "batch.md", kind="idea",
                library_override=str(custom), split=True,
            )

            self.assertTrue((custom / "_INDEX.json").is_file())
            self.assertFalse((workspace / "创意库").exists())


if __name__ == "__main__":
    unittest.main()
