"""MODE_REGISTRY contract: every mode declares an entry type and a real path."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = PROJECT_ROOT / "novel_creation_promax"
REGISTRY = SKILL_ROOT / "MODE_REGISTRY.md"
ALLOWED_TYPES = {"skill", "doc", "kb", "script"}
ENTRY_RE = re.compile(r"`([^`]+)`")


def mode_rows() -> list[list[str]]:
    rows: list[list[str]] = []
    for line in REGISTRY.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if not cells:
            continue
        try:
            int(cells[0])
        except ValueError:
            continue
        rows.append(cells)
    return rows


class ModeRegistryTest(unittest.TestCase):
    def test_every_mode_has_entry_type_and_existing_entry(self):
        rows = mode_rows()
        self.assertEqual(len(rows), 18)

        for cells in rows:
            mode_id, mode_key, entry_type, entry = cells[0], cells[1], cells[4], cells[5]
            with self.subTest(mode=mode_id, key=mode_key):
                self.assertIn(entry_type, ALLOWED_TYPES)

                match = ENTRY_RE.search(entry)
                self.assertIsNotNone(match, f"模式 {mode_id} 必读入口缺少反引号路径")

                ref = match.group(1)
                exists = (PROJECT_ROOT / ref).exists() or (SKILL_ROOT / ref).exists()
                self.assertTrue(exists, f"模式 {mode_id} 必读入口不存在: {ref}")

    def test_table_declares_entry_type_column(self):
        header = next(
            line for line in REGISTRY.read_text(encoding="utf-8").splitlines()
            if line.startswith("| mode_id |")
        )
        self.assertIn("entry_type", header)


if __name__ == "__main__":
    unittest.main()
