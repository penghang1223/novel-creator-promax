"""Regression tests for the absorbed novel-engine tools and thresholds."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "novel_creation_promax" / "scripts"
TOOLS_DIR = PROJECT_ROOT / "tools"
for entry in (PROJECT_ROOT, SCRIPTS_DIR, TOOLS_DIR):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from novel_creation_promax.core import thresholds as T  # noqa: E402
from novel_creation_promax.core.jsonio import save_json  # noqa: E402

import ai_flavor_score  # noqa: E402
import chapter_rhythm  # noqa: E402
import data_diagnosis  # noqa: E402
import emotion_ledger  # noqa: E402
import hit_rate  # noqa: E402
import opening_score  # noqa: E402
import post_write_audit  # noqa: E402
import pre_write_check  # noqa: E402
from story_truth_manager import (  # noqa: E402
    compile_rule_stack,
    write_power_ladder_view,
)


GOOD_OPENING = """第1章 系统觉醒了

“三秒内不还钱，卸你一条腿。”刀疤脸把钢管砸在桌上。

林砚没有退，他盯着对方，突然抓住桌角猛地一掀。债主被撞翻，茶杯碎了一地。代价是右手的旧伤又裂开了，血顺着指缝滴下来。

【叮：危机任务完成，奖励积分10点，解锁技能“反击”。冷却24小时，失败扣除全部积分。】

他咬牙站起，把欠条抢回来，撕成两半。门外传来警笛声，刀疤脸脸色一变。

但林砚知道，真正麻烦的不是这三个混混，而是欠条背后那个名字。

“明天，你还会来吗？”他问。
"""

BAD_OPENING = """第1章 梦的开始

清晨的阳光洒在天空，云朵缓缓飘过，微风拂过大陆的每一个角落。这个世界有着千年前的历史，传说中，帝国曾经无比辉煌，众所周知，万年前的那场战争改变了一切。

他睁开眼，看着陌生的天花板，想起了小时候的事情，又回忆起三年前的传说。这个世界很大，有很多王朝和大陆，据说自古以来就是如此。

他叫小明，今年十八岁。他还有两个朋友，小红、小刚、小美、小强。他们都说，这个世界很危险。

本书慢热，请耐心阅读，后面会越来越精彩。
"""

AI_TEXT = """他缓缓地走进房间，内心深处不禁涌起一阵复杂的情感。与此同时，他仿佛看到了过去的自己——那个无比天真的自己。

他微微皱眉，似乎意识到了什么。因此，他决定进一步调查。然而，他并不知道，这一切都是命运的齿轮开始转动。

他深吸一口气，眼中闪过一丝坚定。首先，他要找到线索；其次，他要确认敌人；最后，他要完成复仇。总而言之，他不会放弃。

他的嘴角勾起一抹淡淡的笑容，毋庸置疑，他已经做好了准备。
"""

HUMAN_TEXT = """“你迟到了七分钟。”老周没抬头，手里的螺丝刀还在转。

林砚把伞靠在门边，水顺着伞骨滴到水泥地上。“楼下保安拦了。”

“他拦你？”老周这才抬眼，看了他一眼，“你翻墙进来的？”

“我刷卡进来的。”林砚把卡放在桌上，指尖还带着雨水，“卡是你给我的，忘了？”

老周盯着那张卡看了两秒，忽然笑了。
"""


class ThresholdTest(unittest.TestCase):
    def test_scripts_share_the_same_thresholds(self):
        self.assertEqual(post_write_audit.WORD_COUNT_MIN, T.WORD_COUNT_MIN)
        self.assertEqual(post_write_audit.DIALOGUE_RATIO_MIN, T.DIALOGUE_RATIO_MIN)
        self.assertEqual(pre_write_check.PASS_THRESHOLD, T.PRE_WRITE_PASS)


class OpeningScoreTest(unittest.TestCase):
    def test_good_opening_scores_higher_than_bad(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp) / "good.md"
            bad = Path(tmp) / "bad.md"
            good.write_text(GOOD_OPENING, encoding="utf-8")
            bad.write_text(BAD_OPENING, encoding="utf-8")

            good_result = opening_score.analyze(good)
            bad_result = opening_score.analyze(bad)

            self.assertGreater(good_result["total"], bad_result["total"])
            self.assertGreaterEqual(good_result["total"], T.OPENING_PASS)
            flag_ids = {item["id"] for item in bad_result["low_retention"]}
            self.assertIn("worldbuilding_dump", flag_ids)
            self.assertIn("weather_opening", flag_ids)
            self.assertIn("dream_wake", flag_ids)


class HitRateTest(unittest.TestCase):
    def _payload(self, **overrides):
        return {"scores": {**{f"D{index}": 8 for index in range(1, 16)}, **overrides}}

    def test_veto_caps_total(self):
        result = hit_rate.evaluate(self._payload(D4=0))

        self.assertLessEqual(result["total"], T.HIT_VETO_CAP)
        self.assertTrue(any("否决项" in item for item in result["cap_reasons"]))

    def test_ceiling_caps_total(self):
        result = hit_rate.evaluate(self._payload(D1=2))

        self.assertLessEqual(result["total"], T.HIT_CEILING_CAP)
        self.assertTrue(any("天花板项" in item for item in result["cap_reasons"]))

    def test_too_many_perfect_scores_are_downgraded(self):
        payload = {"scores": {f"D{index}": 10 for index in range(1, 16)}}
        result = hit_rate.evaluate(payload)

        self.assertTrue(result["honesty_adjustment"])
        self.assertLess(max(result["scores"].values()), 10)


class ChapterRhythmTest(unittest.TestCase):
    def test_bad_table_triggers_r1_r3_r4_r5_r8(self):
        table = """| 章 | 爽点类型 | 钩子 | 字数 |
|---|---|---|---|
| 1 | 日常锚点 | 弱 | 3000 |
| 2 | 日常锚点 | 弱 | 3000 |
| 3 | 日常锚点 | 弱 | 3000 |
| 4 | 日常锚点 | 弱 | 1500 |
| 5 | 日常锚点 | 弱 | 3000 |
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "table.md"
            path.write_text(table, encoding="utf-8")
            result = chapter_rhythm.check(chapter_rhythm.parse_table(path.read_text(encoding="utf-8")))

        codes = {issue["code"] for issue in result["issues"]}
        for code in ("R1", "R3", "R4", "R5", "R8"):
            self.assertIn(code, codes)

    def test_good_table_has_no_issues(self):
        table = """| 章 | 爽点类型 | 钩子 | 字数 |
|---|---|---|---|
| 1 | 身份反转 | 强 | 3000 |
| 2 | 关系推进 | 中 | 3000 |
| 3 | 打脸 | 强 | 3000 |
| 4 | 信息差 | 中 | 3000 |
| 5 | 能力兑现 | 强 | 3000 |
"""
        result = chapter_rhythm.check(chapter_rhythm.parse_table(table))

        self.assertEqual(result["issues"], [])


class AiFlavorTest(unittest.TestCase):
    def test_ai_text_scores_higher_than_human_text(self):
        ai = ai_flavor_score.score(AI_TEXT)
        human = ai_flavor_score.score(HUMAN_TEXT)

        self.assertGreaterEqual(ai["score"], T.AI_FLAVOR_WARN)
        self.assertLess(human["score"], T.AI_FLAVOR_WARN)


class EmotionLedgerTest(unittest.TestCase):
    def test_suffering_streak_and_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = Path(tmp) / "番茄" / "书"
            (novel / "摘要").mkdir(parents=True)
            rows = [
                (1, "受辱", {"tension_peak": 3, "emotion_curve": "压—冷"}, ["苏青被前夫羞辱"]),
                (2, "继续憋屈", {"tension_peak": 2, "emotion_curve": "压—痛"}, ["苏青失去工作"]),
                (3, "反击", {"tension_peak": 9, "emotion_curve": "转—爽"}, ["苏青反击前夫"]),
            ]
            for chapter, title, metrics, events in rows:
                save_json(
                    novel / "摘要" / f"chapter_{chapter:03d}_summary.json",
                    {"chapter": chapter, "title": title, "summary": events[0], "key_events": events, "chapter_metrics": metrics},
                )

            ledger = emotion_ledger.build_ledger(novel)

            self.assertEqual(ledger["chapters"][0]["spark_type"], "受辱/铺垫")
            self.assertEqual(ledger["chapters"][1]["suffering_streak"], 2)
            self.assertEqual(ledger["chapters"][2]["suffering_streak"], 0)
            self.assertEqual(ledger["stats"]["last_release_chapter"], 3)


class DataDiagnosisTest(unittest.TestCase):
    def test_diagnoses_stage_and_front_of_funnel_priority(self):
        data = {
            "words": 120_000,
            "shelf_ratio": 20,
            "ch10_completion": 6,
            "wan_completion": 4,
            "follow7": 4,
            "daily_words": 2000,
            "gap_days": 4,
            "score": 7.2,
        }

        result = data_diagnosis.diagnose(data)

        self.assertEqual(result["stage"], "L3")
        metrics = {issue["metric"] for issue in result["issues"]}
        self.assertIn("断更天数", metrics)
        self.assertIn("日均更新字数", metrics)
        self.assertIn("书架比", metrics)
        self.assertIn("断更", result["causes"][0]["cause"])

    def test_markdown_parsing_handles_wan_and_ratios(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data.md"
            path.write_text(
                "总字数: 12万\n书架比: 1:20\n日均更新: 2000字\n断更天数: 4天\n",
                encoding="utf-8",
            )
            data = data_diagnosis.parse_input(path)

        self.assertEqual(data["words"], 120_000)
        self.assertEqual(data["shelf_ratio"], 20)
        self.assertEqual(data["daily_words"], 2000)
        self.assertEqual(data["gap_days"], 4)


class PostWriteAuditExtraTest(unittest.TestCase):
    def test_new_gate_fields_are_populated(self):
        text = (
            "他感到一阵紧张，她感到害怕，他又感到愤怒。\n\n"
            "“你来了。”他说。\n\n"
            "“我来了。”她道。\n\n"
            "“走吧。”他说。\n\n"
            "“好。”她答。\n\n"
            "他走进房间——又退了出来——再走进去——最后还是停下了。\n\n"
            "他说：这里有问题。她说：什么问题。\n\n"
            "这是一段长度刚好相同的段落内容。\n\n"
            "这也是一段长度刚好相同的段落内容。\n\n"
            "这还是一段长度刚好相同的段落内容。\n\n"
            "你到底想怎么样？"
        )

        result = post_write_audit.audit_chapter(text, "第1章 测试")

        self.assertGreater(result["dash_density"], 0)
        self.assertGreater(result["colon_density"], 0)
        self.assertGreater(result["bare_dialogue_ratio"], 0)
        self.assertGreater(result["emotion_naming_count"], T.EMOTION_NAMING_MAX)
        self.assertTrue(result["chapter_end_issues"])
        self.assertTrue(result["paragraph_uniformity_issues"])


class PowerLadderTest(unittest.TestCase):
    def test_power_ladder_is_compiled_and_rendered(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = Path(tmp) / "番茄" / "书"
            for name in ("摘要", "素材", "设定/真相文件"):
                (novel / name).mkdir(parents=True)
            save_json(
                novel / "设定" / "真相文件" / "characters.json",
                {
                    "schema_version": "1.0",
                    "kind": "characters",
                    "records": [
                        {
                            "id": "char_001",
                            "name": "林砚",
                            "power_ladder": [
                                {"level": "炼气三层", "abilities": ["御火"], "cost": "消耗精血", "obtained_chapter": 3, "cannot_beat": ["筑基"]}
                            ],
                        }
                    ],
                },
            )

            stack = compile_rule_stack(novel, 3, "第3章")
            view = write_power_ladder_view(stack, novel)

            ladder = stack["truth_layers"]["character_knowledge"]["char_001"]["power_ladder"]
            self.assertEqual(ladder[0]["level"], "炼气三层")
            self.assertTrue(view.is_file())
            self.assertIn("炼气三层", view.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
