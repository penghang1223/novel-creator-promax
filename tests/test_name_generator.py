"""Name generator and project-level skill contracts."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "novel_creation_promax" / "scripts" / "name_generator.py"
CLAUDE_SKILLS = PROJECT_ROOT / "skills"

FORBIDDEN_KNOWN_NAMES = {
    "萧炎", "叶凡", "林动", "唐三", "石昊", "韩立",
    "梅长苏", "甄嬛", "若曦", "魏璎珞", "白浅", "夜华",
    "魏无羡", "蓝忘机",
}


def run_generator(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


class NameGeneratorTest(unittest.TestCase):
    def test_generates_names_with_reasons_and_no_mer(self):
        result = run_generator(
            "--gender", "male", "--style", "ancient_elegant", "--count", "5", "--reason"
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        names = [item["full_name"] for item in payload["names"]]
        self.assertEqual(len(names), 5)
        self.assertTrue(all("默" not in name for name in names))
        self.assertTrue(all(item["reason"] for item in payload["names"]))

    def test_avoids_known_character_names(self):
        result = run_generator("--gender", "male", "--style", "xianxia", "--count", "10")

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        names = {item["full_name"] for item in payload["names"]}
        self.assertEqual(names & FORBIDDEN_KNOWN_NAMES, set())

    def test_excludes_existing_names(self):
        first = run_generator("--gender", "female", "--style", "modern", "--count", "5")
        self.assertEqual(first.returncode, 0, first.stderr)
        first_names = [item["full_name"] for item in json.loads(first.stdout)["names"]]

        second = run_generator(
            "--gender", "female", "--style", "modern", "--count", "5",
            "--exclude-names", *first_names,
        )
        self.assertEqual(second.returncode, 0, second.stderr)
        second_names = [item["full_name"] for item in json.loads(second.stdout)["names"]]

        self.assertEqual(set(first_names) & set(second_names), set())


class ProjectSkillTest(unittest.TestCase):
    def test_project_skills_have_frontmatter(self):
        skills = sorted(CLAUDE_SKILLS.glob("*/SKILL.md"))
        self.assertGreaterEqual(len(skills), 1)
        for path in skills:
            with self.subTest(skill=path.parent.name):
                text = path.read_text(encoding="utf-8")
                self.assertTrue(text.startswith("---\n"), path)
                block = text.split("---", 2)[1]
                self.assertIn("name:", block, path)
                self.assertIn("description:", block, path)

    def test_name_generator_skill_wires_existing_tool(self):
        text = (CLAUDE_SKILLS / "name-generator" / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("name_generator.py", text)
        self.assertIn("角色命名指南.md", text)
        self.assertIn("no-mer-names.md", text)
        self.assertIn("禁止出现“默”字", text)
        self.assertIn("设定/真相文件/characters.json", text)


if __name__ == "__main__":
    unittest.main()
