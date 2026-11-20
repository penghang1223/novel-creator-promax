"""Auxiliary plugin skills: wiring and path contracts.

These skills used to live under ``.claude/skills`` and were not distributed.
They now ship with the plugin under ``skills/`` so third-party installs get
the same capability set.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = PROJECT_ROOT / "skills"
PLUGIN_PATH_RE = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\s`\"'）)]+)")

AUXILIARY_SKILLS = {
    "chapter-hook",
    "data-diagnosis",
    "deai-check",
    "idea-library",
    "name-generator",
    "platform-format",
    "title-blurb",
}


def skill_files() -> list[Path]:
    return sorted(
        path for path in SKILLS_ROOT.glob("*/SKILL.md") if path.parent.name in AUXILIARY_SKILLS
    )


def frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    result: dict[str, str] = {}
    for line in text[4:end].splitlines():
        key, separator, value = line.partition(":")
        if separator:
            result[key.strip()] = value.strip()
    return result


class ProjectSkillContractTest(unittest.TestCase):
    def test_all_project_skills_have_frontmatter_and_boundary(self):
        files = skill_files()
        self.assertGreaterEqual(len(files), 7)
        for path in files:
            with self.subTest(skill=path.parent.name):
                text = path.read_text(encoding="utf-8")
                meta = frontmatter(path)
                self.assertEqual(meta.get("name"), path.parent.name)
                self.assertTrue(meta.get("description"))
                self.assertIn("## 职责", text)
                self.assertIn("## 硬规则", text)
                self.assertTrue("不写插件" in text or "工作区" in text)

    def test_plugin_root_paths_exist(self):
        missing: list[str] = []
        for path in skill_files():
            for relative in PLUGIN_PATH_RE.findall(path.read_text(encoding="utf-8")):
                cleaned = relative.rstrip("。，；：、")
                if any(token in cleaned for token in ("{", "}", "*")):
                    continue
                target = PROJECT_ROOT / cleaned
                if not target.exists():
                    missing.append(f"{path.parent.name}: {cleaned}")
        self.assertEqual(missing, [], "\n".join(missing))

    def test_skill_specific_wiring(self):
        expectations = {
            "chapter-hook": [
                "knowledge_base/40_Writing/01_开篇技巧/开头钩子库.md",
                "novel_creation_promax/scripts/post_write_audit.py",
                "tools/chapter_rhythm.py",
            ],
            "title-blurb": [
                "knowledge_base/40_Writing/04_场景与描写/书名与简介.md",
                "knowledge_base/60_Platform/_PROFILES.json",
            ],
            "deai-check": [
                "tools/ai_flavor_score.py",
                "knowledge_base/40_Writing/05_降AI痕迹/朱雀祛AI味五维.md",
                "knowledge_base/40_Writing/05_降AI痕迹/AI禁用词与句式表.md",
            ],
            "platform-format": [
                "knowledge_base/60_Platform/_PROFILES.json",
                "knowledge_base/60_Platform/平台规则.md",
                "auto_publish/fanqie_auto_publish",
            ],
            "data-diagnosis": [
                "tools/data_diagnosis.py",
                "knowledge_base/60_Platform/数据诊断与救盘.md",
                "skills/novel-diagnose/SKILL.md",
            ],
            "name-generator": [
                "novel_creation_promax/scripts/name_generator.py",
                "knowledge_base/20_Characters/角色命名指南.md",
            ],
            "idea-library": [
                "tools/idea_library.py",
                "创意库/",
                "_INDEX.md",
            ],
        }
        for skill, needles in expectations.items():
            text = (SKILLS_ROOT / skill / "SKILL.md").read_text(encoding="utf-8")
            with self.subTest(skill=skill):
                for needle in needles:
                    self.assertIn(needle, text)


if __name__ == "__main__":
    unittest.main()
