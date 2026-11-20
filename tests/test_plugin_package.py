"""Plugin packaging contracts: manifest, skills, commands and doctor."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ROOT_ENV_KEYS = ("CLAUDE_PLUGIN_ROOT", "CLAUDE_PROJECT_DIR", "NOVEL_PLUGIN_ROOT", "NOVEL_WORKSPACE_ROOT")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class ManifestTest(unittest.TestCase):
    def test_plugin_and_marketplace_names_match(self):
        plugin = load_json(PROJECT_ROOT / ".claude-plugin" / "plugin.json")
        marketplace = load_json(PROJECT_ROOT / ".claude-plugin" / "marketplace.json")

        self.assertEqual(plugin["name"], "novel-creator-pro")
        self.assertTrue(plugin.get("version"))
        self.assertEqual(plugin["version"], (PROJECT_ROOT / "VERSION").read_text(encoding="utf-8").strip())
        self.assertEqual(marketplace["plugins"][0]["name"], plugin["name"])
        self.assertEqual(marketplace["plugins"][0]["source"], "./")


class ComponentTest(unittest.TestCase):
    def test_skills_have_unique_frontmatter(self):
        skills = sorted((PROJECT_ROOT / "skills").glob("*/SKILL.md"))
        self.assertGreaterEqual(len(skills), 7)
        names: list[str] = []
        for skill in skills:
            text = skill.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---"), skill)
            block = text.split("---", 2)[1]
            self.assertIn("name:", block, skill)
            self.assertIn("description:", block, skill)
            names.append(skill.parent.name)
        self.assertEqual(len(names), len(set(names)))

    def test_commands_have_frontmatter(self):
        commands = sorted((PROJECT_ROOT / "commands").glob("*.md"))
        self.assertGreaterEqual(len(commands), 9)
        for command in commands:
            text = command.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---"), command)
            self.assertIn("description:", text.split("---", 2)[1], command)

    def test_market_and_idea_assets_exist(self):
        for relative in (
            "skills/novel-market-research/SKILL.md",
            "skills/novel-idea/SKILL.md",
            "skills/novel-workflow/SKILL.md",
            "commands/research.md",
            "commands/idea.md",
            "commands/workflow.md",
            "novel_creation_promax/references/templates/market_research_report.md",
            "novel_creation_promax/references/templates/idea_card.md",
            "tools/idea_score.py",
            "tools/workflow.py",
            "docs/WORKFLOW.md",
        ):
            self.assertTrue((PROJECT_ROOT / relative).is_file(), relative)

        registry = (PROJECT_ROOT / "novel_creation_promax" / "MODE_REGISTRY.md").read_text(encoding="utf-8")
        self.assertIn("| 14 | market-research |", registry)
        self.assertIn("| 15 | idea-generation |", registry)
        self.assertIn("| 16 | workflow |", registry)

        idea_skill = (PROJECT_ROOT / "skills" / "novel-idea" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("没有维度低于 8", idea_skill)

    def test_hooks_reference_existing_files(self):
        hooks = load_json(PROJECT_ROOT / "hooks" / "hooks.json")["hooks"]
        for event in hooks.values():
            for group in event:
                for handler in group["hooks"]:
                    for arg in handler.get("args", []):
                        if "${CLAUDE_PLUGIN_ROOT}" in arg:
                            path = PROJECT_ROOT / arg.replace("${CLAUDE_PLUGIN_ROOT}/", "")
                            self.assertTrue(path.is_file(), path)


class DoctorTest(unittest.TestCase):
    def test_doctor_runs_without_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {key: value for key, value in os.environ.items() if key not in ROOT_ENV_KEYS}
            result = subprocess.run(
                [sys.executable, str(PROJECT_ROOT / "tools" / "plugin_doctor.py"), "--json", "--root", tmp],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["summary"]["errors"], 0)
            self.assertGreater(report["summary"]["checks"], 10)


if __name__ == "__main__":
    unittest.main()
