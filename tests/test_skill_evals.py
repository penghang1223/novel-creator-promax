"""Behavior eval harness regression tests.

These tests do two things:

1. Run the shipped eval suite and require every case to pass.
2. Feed the runner a deliberately broken case and require it to fail, so a
   broken evaluator cannot silently report all-green.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_evals(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "tools" / "run_skill_evals.py"), *args],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


class ShippedEvalTest(unittest.TestCase):
    def test_all_shipped_evals_pass(self):
        result = run_evals("--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)

        self.assertEqual(report["schema_version"], "skill-eval-report/v1")
        self.assertGreaterEqual(report["summary"]["cases"], 10)
        self.assertEqual(report["summary"]["failed"], 0)
        ids = {item["id"] for item in report["results"]}
        for expected in (
            "all-skills-frontmatter",
            "write-skill-step-order",
            "review-skill-json-first",
            "orchestrator-stage-order",
            "agents-exist-and-read-only",
            "review-cli-blocked-template-to-pass",
            "command-write-matches-chapter-skill",
            "mode-registry-matches-latest-flow",
            "commands-doc-writing-chain",
            "pre-write-blocks-critical-unknown-facts",
            "review-basis-stale-when-rule-stack-appears",
            "reader-truth-cli-sync",
            "opening-score-cli",
            "data-diagnosis-cli",
            "chapter-rhythm-cli",
            "ai-flavor-cli",
        ):
            self.assertIn(expected, ids)


class RunnerSelfTest(unittest.TestCase):
    def test_runner_detects_missing_required_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            evals_dir = Path(tmp)
            (evals_dir / "broken.json").write_text(
                json.dumps(
                    {
                        "cases": [
                            {
                                "id": "deliberately-broken",
                                "type": "text_contract",
                                "path": "skills/novel-chapter-write/SKILL.md",
                                "required": ["这段文字不应该存在-9427"],
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = run_evals("--evals-dir", str(evals_dir), "--json")

            self.assertEqual(result.returncode, 1)
            report = json.loads(result.stdout)
            self.assertEqual(report["summary"]["failed"], 1)
            self.assertEqual(report["results"][0]["id"], "deliberately-broken")

    def test_runner_rejects_unknown_case_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            evals_dir = Path(tmp)
            (evals_dir / "unknown.json").write_text(
                json.dumps(
                    {
                        "cases": [
                            {"id": "unknown-type", "type": "not_a_real_type"}
                        ]
                    }
                ),
                encoding="utf-8",
            )

            result = run_evals("--evals-dir", str(evals_dir), "--json")

            self.assertEqual(result.returncode, 1)
            report = json.loads(result.stdout)
            self.assertEqual(report["summary"]["failed"], 1)
            self.assertIn("unknown case type", report["results"][0]["reason"])


if __name__ == "__main__":
    unittest.main()
