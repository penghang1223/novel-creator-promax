"""章节快照备份测试。"""

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

from novel_creation_promax.core.chapter_backup import (  # noqa: E402
    list_snapshots,
    snapshot_chapter,
)

TOOL = PROJECT_ROOT / "tools" / "backup.py"


def make_book(tmp: str) -> Path:
    workspace = Path(tmp) / "ws"
    book = workspace / "novel_output" / "番茄" / "测试书"
    (book / "正文").mkdir(parents=True)
    (book / "设定" / "真相文件").mkdir(parents=True)
    (book / "摘要").mkdir()
    (book / "记忆").mkdir()
    (book / "素材" / "commits").mkdir(parents=True)

    (book / "正文" / "第001章-开始.md").write_text("第1章正文", encoding="utf-8")
    (book / "设定" / "人物档案.md").write_text("# 人物档案", encoding="utf-8")
    (book / "设定" / "真相文件" / "characters.json").write_text(
        json.dumps({"records": []}, ensure_ascii=False), encoding="utf-8"
    )
    (book / "摘要" / "chapter_001_passport.json").write_text(
        json.dumps({"chapter": 1}, ensure_ascii=False), encoding="utf-8"
    )
    (book / "记忆" / "style_dna.json").write_text("{}", encoding="utf-8")
    (book / "novel_state.json").write_text(
        json.dumps({"title": "测试书", "platform": "番茄"}, ensure_ascii=False), encoding="utf-8"
    )
    (book / "素材" / "commits" / "chapter_001.commit.json").write_text(
        json.dumps({"chapter": 1, "status": "accepted"}, ensure_ascii=False), encoding="utf-8"
    )
    return book


class ChapterBackupTest(unittest.TestCase):
    def test_snapshot_copies_body_settings_state_and_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            book = make_book(tmp)
            summary = snapshot_chapter(
                book, 1, reason="test", keep=5, timestamp="20260101_000000_000000"
            )
            root = Path(summary["path"])
            self.assertTrue((root / "_manifest.json").is_file())
            self.assertTrue((root / "正文" / "第001章-开始.md").is_file())
            self.assertTrue((root / "设定" / "人物档案.md").is_file())
            self.assertTrue((root / "设定" / "真相文件" / "characters.json").is_file())
            self.assertTrue((root / "摘要" / "chapter_001_passport.json").is_file())
            self.assertTrue((root / "记忆" / "style_dna.json").is_file())
            self.assertTrue((root / "novel_state.json").is_file())
            self.assertTrue((root / "素材" / "commits" / "chapter_001.commit.json").is_file())

            manifest = json.loads((root / "_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["chapter"], 1)
            self.assertEqual(manifest["reason"], "test")
            self.assertGreaterEqual(len(manifest["files"]), 7)

            rows = list_snapshots(book, 1)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["chapter"], 1)

    def test_keep_prunes_old_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            book = make_book(tmp)
            for index in range(3):
                snapshot_chapter(
                    book,
                    1,
                    keep=2,
                    timestamp=f"20260101_00000{index}_000000",
                )
            snapshots = list((book / "素材" / "备份").glob("chapter_001_*"))
            self.assertEqual(len(snapshots), 2)

    def test_cli_snapshot_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            book = make_book(tmp)
            result = subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "snapshot",
                    "--novel-dir",
                    str(book),
                    "--chapter",
                    "1",
                    "--reason",
                    "cli",
                    "--json",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["chapter"], 1)
            self.assertTrue(Path(payload["path"]).is_dir())


if __name__ == "__main__":
    unittest.main()
