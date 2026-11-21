"""章节 / 场景 spec 工具测试。"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOL = PROJECT_ROOT / "tools" / "chapter_spec.py"


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOL), *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def valid_spec() -> dict:
    return {
        "chapter": 12,
        "title": "第12章 对账",
        "summary": "姜照当众合龙门，差额指向北境饷案。",
        "before_state": {"characters": [{"name": "姜照", "state": "被贬", "location": "废卷库"}], "plot_hooks": []},
        "after_state": {"characters": [{"name": "姜照", "state": "拿到半印", "location": "废卷库"}], "plot_advances": []},
        "must_happen": ["合龙门", "发现半印"],
        "scenes": [
            {
                "type": "主要",
                "goal": "当众念平差额",
                "result": "账平了，但秦姑姑被拖走",
                "outside": ["行动：逐项念账", "阻碍：曹福来打断", "助力：苏檀递批回"],
                "inside": ["反应：手抖", "消化：父亲旧案", "选择：继续查", "决定：夜入废卷库"],
                "narration": "只写姜照能看到的账册与在场反应",
                "scale": "扩展",
            }
        ],
        "tension_curve": [
            {"position": 0, "value": 3, "note": "铺垫"},
            {"position": 50, "value": 8, "note": "合龙门"},
            {"position": 100, "value": 5, "note": "余波"},
        ],
        "change": "信息",
        "new_hooks": ["半印上的“北”字"],
    }


class ChapterSpecTest(unittest.TestCase):
    def test_scaffold_then_validate(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "spec.json"
            scaffold = run("scaffold", "--chapter", "12", "--title", "第12章 对账", "--output", str(path))
            self.assertEqual(scaffold.returncode, 0, scaffold.stderr)
            self.assertTrue(path.is_file())

            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["chapter"], 12)
            self.assertEqual(payload["change"], "信息")

            validate = run("validate", "--file", str(path), "--json")
            self.assertEqual(validate.returncode, 1)
            report = json.loads(validate.stdout)
            self.assertEqual(report["status"], "fail")
            self.assertTrue(report["errors"])

    def test_valid_spec_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "spec.json"
            path.write_text(json.dumps(valid_spec(), ensure_ascii=False), encoding="utf-8")
            result = run("validate", "--file", str(path), "--json")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["status"], "pass")
            self.assertEqual(report["errors"], [])

    def test_result_equal_goal_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = valid_spec()
            spec["scenes"][0]["result"] = spec["scenes"][0]["goal"]
            path = Path(tmp) / "spec.json"
            path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
            result = run("validate", "--file", str(path), "--json")
            self.assertEqual(result.returncode, 1)
            report = json.loads(result.stdout)
            self.assertTrue(any("result 不能等于 goal" in item for item in report["errors"]))

    def test_missing_inside_and_short_outside_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = valid_spec()
            spec["scenes"][0]["inside"] = []
            spec["scenes"][0]["outside"] = ["行动：只有一个"]
            path = Path(tmp) / "spec.json"
            path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
            result = run("validate", "--file", str(path), "--json")
            report = json.loads(result.stdout)
            self.assertTrue(any("inside" in item for item in report["errors"]))
            self.assertTrue(any("outside 至少 3 轮" in item for item in report["errors"]))

    def test_invalid_change_and_curve_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = valid_spec()
            spec["change"] = "随便"
            spec["tension_curve"] = [
                {"position": 50, "value": 8},
                {"position": 0, "value": 3},
            ]
            path = Path(tmp) / "spec.json"
            path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
            result = run("validate", "--file", str(path), "--json")
            report = json.loads(result.stdout)
            self.assertTrue(any("change" in item for item in report["errors"]))
            self.assertTrue(any("升序" in item for item in report["errors"]))

    def test_to_scene_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_path = Path(tmp) / "spec.json"
            plan_path = Path(tmp) / "scene_plan.json"
            spec_path.write_text(json.dumps(valid_spec(), ensure_ascii=False), encoding="utf-8")
            result = run(
                "to-scene-plan",
                "--file",
                str(spec_path),
                "--output",
                str(plan_path),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            self.assertEqual(len(plan), 1)
            self.assertEqual(plan[0]["goal"], "当众念平差额")
            self.assertEqual(plan[0]["outcome"], "账平了，但秦姑姑被拖走")
            self.assertTrue(plan[0]["constraints"])


if __name__ == "__main__":
    unittest.main()
