"""创意五维评分工具测试。"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import idea_score  # noqa: E402

DIMENSIONS = ("innovation", "market", "readability", "emotion", "commercial")


def scores(**values: int) -> dict:
    return {"title": "测试创意", "scores": {**{key: 8 for key in DIMENSIONS}, **values}}


class ScoreTest(unittest.TestCase):
    def test_perfect_scores(self):
        result = idea_score.score_idea(scores(**{key: 10 for key in DIMENSIONS}))

        self.assertEqual(result["total"], 100.0)
        self.assertEqual(result["grade"], "S")
        self.assertEqual(result["weakest"], [])

    def test_weighted_total_and_grade(self):
        result = idea_score.score_idea(
            scores(innovation=6, market=8, readability=7, emotion=9, commercial=5)
        )

        self.assertEqual(result["total"], 72.5)
        self.assertEqual(result["grade"], "B")
        self.assertEqual(result["weakest"], ["commercial", "innovation", "readability"])

    def test_high_total_with_weak_dimension_recommends_fix(self):
        result = idea_score.score_idea(
            scores(innovation=6, market=10, readability=10, emotion=10, commercial=10)
        )

        self.assertEqual(result["total"], 96.0)
        self.assertEqual(result["grade"], "S")
        self.assertIn("先补强", result["recommendation"])
        self.assertIn("创新性", result["recommendation"])

    def test_missing_dimension_is_rejected(self):
        payload = {"title": "缺项", "scores": {"innovation": 8}}
        with self.assertRaises(ValueError):
            idea_score.score_idea(payload)

    def test_out_of_range_is_rejected(self):
        with self.assertRaises(ValueError):
            idea_score.score_idea(scores(innovation=11))
        with self.assertRaises(ValueError):
            idea_score.score_idea(scores(market=-1))

    def test_non_numeric_is_rejected(self):
        with self.assertRaises(ValueError):
            idea_score.score_idea(scores(emotion="高"))


class CliTest(unittest.TestCase):
    def _run(self, payload: dict) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "idea.json"
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(TOOLS_DIR / "idea_score.py"), "--input", str(path), "--json"],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

    def test_cli_outputs_json(self):
        result = self._run(scores(**{key: 10 for key in DIMENSIONS}))

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["total"], 100.0)

    def test_cli_returns_two_on_invalid_input(self):
        result = self._run({"title": "缺项", "scores": {"innovation": 8}})

        self.assertEqual(result.returncode, 2)
        self.assertIn("error", result.stderr.lower())


if __name__ == "__main__":
    unittest.main()
