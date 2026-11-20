"""技能路由与职责边界的回归测试。"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = PROJECT_ROOT / "novel_creation_promax"
SKILL_NAMES = (
    "novel-project-planning",
    "novel-memory",
    "novel-review",
    "novel-publish",
    "novel-knowledge-ingestion",
)


class SkillArchitectureTest(unittest.TestCase):
    def test_subskills_define_frontmatter_and_boundaries(self):
        for name in SKILL_NAMES:
            with self.subTest(skill=name):
                content = (PROJECT_ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
                self.assertTrue(content.startswith("---\n"))
                self.assertIn("name:", content)
                self.assertIn("description:", content)
                self.assertIn("## 边界", content)
                self.assertIn("## 禁止事项", content)

    def test_main_skill_routes_by_capability_not_chapter_microsteps(self):
        content = (PROJECT_ROOT / "skills" / "novel-creator" / "SKILL.md").read_text(encoding="utf-8")
        for ref in (
            "skills/novel-project-planning/SKILL.md",
            "skills/novel-memory/SKILL.md",
            "skills/novel-review/SKILL.md",
            "skills/novel-publish/SKILL.md",
            "skills/novel-knowledge-ingestion/SKILL.md",
            "references/orchestrator.md",
        ):
            self.assertIn(ref, content)
        self.assertIn("不建立独立 skill", content)

    def test_health_check_validates_skill_composition(self):
        result = subprocess.run(
            [sys.executable, "novel_creation_promax/scripts/skill_health_check.py"],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("== skill contracts ==", result.stdout)
        self.assertIn("errors=0 warnings=0", result.stdout)


if __name__ == "__main__":
    unittest.main()
