"""Subagent contracts: frontmatter, read-only permissions and skill wiring."""

from __future__ import annotations

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = PROJECT_ROOT / "agents"
EXPECTED_AGENTS = ("context-agent.md", "reviewer.md", "data-agent.md")


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


class AgentContractTest(unittest.TestCase):
    def test_agents_exist_with_required_frontmatter(self):
        for name in EXPECTED_AGENTS:
            with self.subTest(agent=name):
                path = AGENT_ROOT / name
                self.assertTrue(path.is_file(), path)
                fm = frontmatter(path)
                self.assertEqual(fm.get("name"), name.removesuffix(".md"))
                self.assertTrue(fm.get("description"))
                self.assertTrue(fm.get("tools"))

    def test_agents_are_read_only(self):
        for name in EXPECTED_AGENTS:
            with self.subTest(agent=name):
                tools = frontmatter(AGENT_ROOT / name).get("tools", "")
                self.assertNotIn("Write", tools)
                self.assertNotIn("Edit", tools)
                self.assertIn("Read", tools)

    def test_reviewer_defines_strict_json_contract(self):
        text = (AGENT_ROOT / "reviewer.md").read_text(encoding="utf-8")
        for key in (
            "blocking_count",
            "dimensions",
            "dialogue",
            "coolpoint",
            "structure",
            "anti_ai",
            "reading_power",
            "target",
            "sha256",
            "revision_id",
            "revision_version",
            "basis",
            "expected_versions",
            "input_fingerprint",
            "source_refs",
            "truth_layers",
            "POV_LEAK",
            "code",
            "只返回",
        ):
            self.assertIn(key, text)

    def test_context_agent_requires_five_sections_and_blocker(self):
        text = (AGENT_ROOT / "context-agent.md").read_text(encoding="utf-8")
        for key in ("开篇委托", "这章的故事", "这章的人物", "怎么写更顺", "收在哪里", "BLOCKER"):
            self.assertIn(key, text)

    def test_data_agent_aligns_with_truth_delta_schema(self):
        text = (AGENT_ROOT / "data-agent.md").read_text(encoding="utf-8")
        for key in (
            "chapter_observations",
            "proposed_updates",
            "continuity_risks",
            "auto_extraction",
            "review_status",
            "approved",
            "no_changes",
        ):
            self.assertIn(key, text)


class SkillWiringTest(unittest.TestCase):
    def test_write_skill_calls_agents_in_order(self):
        text = (PROJECT_ROOT / "skills" / "novel-chapter-write" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        context_pos = text.find("novel-creator-pro:context-agent")
        pass1_pos = text.find("只依据任务书起草 Pass 1")
        reviewer_pos = text.find("novel-creator-pro:reviewer")
        post_pos = text.find("write_pipeline.py\" post")
        self.assertGreaterEqual(context_pos, 0)
        self.assertGreaterEqual(reviewer_pos, 0)
        self.assertLess(context_pos, pass1_pos)
        self.assertLess(reviewer_pos, post_pos)

    def test_review_skill_is_json_first(self):
        text = (PROJECT_ROOT / "skills" / "novel-review" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("novel-creator-pro:reviewer", text)
        self.assertIn("chapter_NNN_review.json", text)
        self.assertIn("tools/review_result.py", text)
        self.assertIn("不得手改字段", text)

    def test_orchestrator_declares_new_stages(self):
        text = (
            PROJECT_ROOT
            / "novel_creation_promax"
            / "references"
            / "orchestrator.md"
        ).read_text(encoding="utf-8")
        self.assertIn("3.5 写作任务书", text)
        self.assertIn("5.5 结构化审稿", text)
        self.assertIn("context-agent", text)
        self.assertIn("reviewer", text)


if __name__ == "__main__":
    unittest.main()
