"""Author truth / reader-known truth layers and derived views."""

from __future__ import annotations

import json
import subprocess
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
    collect_truth_layers,
    compile_rule_stack,
    write_truth_brief,
    write_truth_views,
)


def make_novel(tmp: str) -> Path:
    novel = Path(tmp) / "番茄" / "测试书"
    for name in ("正文", "摘要", "素材", "设定/真相文件"):
        (novel / name).mkdir(parents=True)
    return novel


def write_truth(novel: Path) -> None:
    save_json(
        novel / "设定" / "真相文件" / "events.json",
        {
            "schema_version": "1.0",
            "kind": "events",
            "records": [
                {
                    "id": "evt_001",
                    "name": "旧案",
                    "status": "done",
                    "cause": "旧案发生",
                    "effect": "读者已经知道旧案",
                    "reader_known": True,
                    "reveal_status": "已揭示",
                    "reveal_chapter": 3,
                },
                {
                    "id": "evt_002",
                    "name": "真凶",
                    "status": "planned",
                    "cause": "真凶出手",
                    "effect": "真凶是主角父亲",
                    "reader_known": False,
                    "reveal_status": "未揭示",
                    "reveal_chapter": 20,
                },
                {
                    "id": "evt_003",
                    "name": "未来事件",
                    "status": "planned",
                    "cause": "未来",
                    "effect": "第30章才揭示",
                    "reveal_status": "已揭示",
                    "reveal_chapter": 30,
                },
            ],
        },
    )
    save_json(
        novel / "设定" / "真相文件" / "foreshadowing.json",
        {
            "schema_version": "1.0",
            "kind": "foreshadowing",
            "records": [
                {
                    "id": "fo_001",
                    "plant_chapter": 2,
                    "content": "一封匿名信",
                    "payoff_plan": "信是母亲写的",
                    "status": "planned",
                    "reader_known": True,
                    "reveal_status": "未揭示",
                }
            ],
        },
    )
    save_json(
        novel / "设定" / "真相文件" / "characters.json",
        {
            "schema_version": "1.0",
            "kind": "characters",
            "records": [
                {
                    "id": "char_001",
                    "name": "林砚",
                    "knowledge_boundary": ["旧案"],
                    "secrets": ["父亲是真凶"],
                }
            ],
        },
    )


class TruthLayerTest(unittest.TestCase):
    def test_event_layers_respect_reveal_chapter(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            write_truth(novel)

            layers = collect_truth_layers(novel, 12)

            reader_ids = {item["id"] for item in layers["reader_known"]}
            unrevealed_ids = {item["id"] for item in layers["unrevealed_facts"]}
            self.assertIn("evt_001", reader_ids)
            self.assertIn("evt_002", unrevealed_ids)
            self.assertIn("evt_003", unrevealed_ids)
            self.assertNotIn("evt_003", reader_ids)

    def test_foreshadowing_splits_hook_and_payoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            write_truth(novel)

            layers = collect_truth_layers(novel, 12)

            reader_types = {(item["type"], item["id"]) for item in layers["reader_known"]}
            unrevealed_types = {(item["type"], item["id"]) for item in layers["unrevealed_facts"]}
            self.assertIn(("foreshadowing_hook", "fo_001"), reader_types)
            self.assertIn(("foreshadowing_payoff", "fo_001"), unrevealed_types)

    def test_character_knowledge_and_author_only_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            write_truth(novel)

            layers = collect_truth_layers(novel, 12)

            character = layers["character_knowledge"]["char_001"]
            self.assertEqual(character["knows"], ["旧案"])
            self.assertEqual(character["author_only"], ["父亲是真凶"])

    def test_compile_rule_stack_includes_truth_layers(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            write_truth(novel)

            stack = compile_rule_stack(novel, 12, "第12章")

            self.assertIn("truth_layers", stack)
            self.assertGreaterEqual(len(stack["truth_layers"]["unrevealed_facts"]), 2)
            self.assertTrue(
                any("reader_known" in item for item in stack["must_check_before_writing"])
            )

    def test_truth_brief_and_views(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            write_truth(novel)
            stack = compile_rule_stack(novel, 12, "第12章")
            brief = novel / "素材" / "brief.md"

            write_truth_brief(stack, brief)
            views = write_truth_views(stack, novel)

            brief_text = brief.read_text(encoding="utf-8")
            self.assertIn("作者真相", brief_text)
            self.assertIn("读者已知", brief_text)
            self.assertIn("未揭示事实", brief_text)
            self.assertEqual({path.name for path in views}, {"作者真相.md", "读者已知.md"})
            self.assertIn("林砚", json.dumps(stack["truth_layers"]["character_knowledge"], ensure_ascii=False))


class ReaderTruthCliTest(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "tools" / "reader_truth.py"), *args],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_sync_show_and_validate(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = make_novel(tmp)
            write_truth(novel)

            sync = self.run_cli("sync", "--novel-dir", str(novel), "--chapter", "12")
            self.assertEqual(sync.returncode, 0, sync.stdout + sync.stderr)
            self.assertTrue((novel / "追踪" / "时间线" / "作者真相.md").is_file())
            self.assertTrue((novel / "追踪" / "时间线" / "读者已知.md").is_file())

            show = self.run_cli(
                "show", "--novel-dir", str(novel), "--chapter", "12", "--layer", "unrevealed", "--json"
            )
            self.assertEqual(show.returncode, 0, show.stdout + show.stderr)
            self.assertIn("evt_002", show.stdout)

            validate = self.run_cli("validate", "--novel-dir", str(novel), "--chapter", "12")
            self.assertEqual(validate.returncode, 0, validate.stdout + validate.stderr)


if __name__ == "__main__":
    unittest.main()
