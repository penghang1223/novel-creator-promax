"""core 包回归测试（stdlib unittest，无需额外依赖）。

运行：
    python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from novel_creation_promax.core import audit_schema, paths  # noqa: E402
from novel_creation_promax.core.chapter_commit import (  # noqa: E402
    record_chapter_commit,
    verify_chapter_commit,
)
from novel_creation_promax.core.chapter_workflow import (  # noqa: E402
    chapter_lock,
    init_workflow,
    transition,
)
from novel_creation_promax.core.contracts import (  # noqa: E402
    validate_chapter_summary,
    validate_project_state,
)
from novel_creation_promax.core.knowledge_index import search_knowledge, sync_knowledge_index  # noqa: E402
from novel_creation_promax.core.gate import verify_bootstrap_gate  # noqa: E402
from novel_creation_promax.core.passport import normalize_status  # noqa: E402
from novel_creation_promax.core.platform_profiles import (  # noqa: E402
    evaluate_word_count,
    load_platform_profile,
    platform_for_novel_dir,
)
from novel_creation_promax.core.project_registry import build_registry  # noqa: E402
from novel_creation_promax.core.project_state import ensure_state_shape, migrate_state_file  # noqa: E402
from novel_creation_promax.core.run_ledger import append_run, infer_run_context, load_runs  # noqa: E402
from novel_creation_promax.core.revision_control import (  # noqa: E402
    create_proposal,
    create_snapshot,
    restore_snapshot,
    review_proposal,
)
from novel_creation_promax.core.story_index import (  # noqa: E402
    index_path,
    project_key,
    query_chapters,
    query_projects,
    sync_root_index,
)
from novel_creation_promax.core.scene_passport import (  # noqa: E402
    initialize_scene_plan,
    list_scene_passports,
    transition_scene,
)
from novel_creation_promax.core.quality_profiles import quality_profile  # noqa: E402
from novel_creation_promax.core.tension_curve import estimate_tension_curve, validate_tension_curve  # noqa: E402


class ChapterDiscoveryTest(unittest.TestCase):
    def test_recursive_and_dedup(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = Path(tmp) / "书"
            body = novel / "正文"
            (body / "第一卷").mkdir(parents=True)
            (body / "第001章-开始.md").write_text("x", encoding="utf-8")
            (body / "第一卷" / "第002章-继续.md").write_text("x", encoding="utf-8")
            (body / "第一卷" / "第002章-重复.md").write_text("x", encoding="utf-8")
            (body / "full_review_report.md").write_text("误放报告", encoding="utf-8")
            (body / "notes.json").write_text("{}", encoding="utf-8")

            found = paths.list_chapter_files(novel)
            numbers = [chapter for chapter, _ in found]
            self.assertEqual(numbers, [1, 2])
            # 同名章号只保留一份
            self.assertEqual(len(found), 2)

    def test_find_memory_dir_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = Path(tmp) / "书"
            (novel / "memory").mkdir(parents=True)
            self.assertEqual(paths.find_memory_dir(novel).name, "memory")
            (novel / "记忆").mkdir()
            self.assertEqual(paths.find_memory_dir(novel).name, "记忆")

    def test_novel_dir_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            with self.assertRaises(ValueError):
                paths.get_novel_dir(output, "番茄", "../outside")
            with self.assertRaises(ValueError):
                paths.get_novel_dir(output, "../outside", "book")

    def test_get_memory_dir_preserves_existing_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            novel = output / "番茄" / "book"
            (novel / "memory").mkdir(parents=True)
            self.assertEqual(paths.get_memory_dir(output, "番茄", "book"), novel / "memory")

    def test_infer_chapter_number_patterns(self):
        self.assertEqual(paths.infer_chapter_number(Path("第012章-x.md")), 12)
        self.assertEqual(paths.infer_chapter_number(Path("012_x.md")), 12)
        self.assertEqual(paths.infer_chapter_number(Path("chapter_12.md")), 12)
        self.assertIsNone(paths.infer_chapter_number(Path("report.md")))


class AuditSchemaTest(unittest.TestCase):
    def test_legacy_flat_payload(self):
        flat = {
            "ai_words": {"突然": 3, "沉默": 0, "像是": 1},
            "dialogue_ratio": 0.31,
            "word_count": 2950,
            "pass": False,
            "warnings": ["w1"],
        }
        canonical = audit_schema.canonicalize(audit_schema.unwrap_audit(flat), chapter=7)
        self.assertEqual(canonical["chapter"], 7)
        self.assertEqual(canonical["status"], "fail")
        self.assertEqual(canonical["dialogue_ratio"], 0.31)
        self.assertEqual(canonical["word_count"], 2950)
        # 只保留出现次数 > 0 的词
        self.assertEqual(
            sorted(item["word"] for item in canonical["ai_words"]),
            ["像是", "突然"],
        )

    def test_wrapped_payload(self):
        wrapped = {
            "generated_at": "2026-01-01T00:00:00",
            "status": "passed",
            "results": {
                "ai_words": {"突然": 2},
                "dialogue_ratio": {"ratio": 0.42},
                "word_count": {"count": 3100, "min": 2000},
                "warnings": [],
            },
        }
        canonical = audit_schema.canonicalize(audit_schema.unwrap_audit(wrapped))
        self.assertEqual(canonical["status"], "pass")
        self.assertAlmostEqual(canonical["dialogue_ratio"], 0.42)
        self.assertEqual(canonical["word_count"], 3100)
        self.assertEqual(canonical["format"], "wrapped")

    def test_find_audit_report_variants(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = Path(tmp) / "书"
            (novel / "素材").mkdir(parents=True)
            (novel / "摘要").mkdir(parents=True)
            (novel / "素材" / "audit_ch2.json").write_text("{}", encoding="utf-8")
            (novel / "摘要" / "chapter_003_audit.json").write_text("{}", encoding="utf-8")
            self.assertEqual(audit_schema.find_audit_report(novel, 2).parent.name, "素材")
            self.assertEqual(audit_schema.find_audit_report(novel, 3).parent.name, "摘要")
            self.assertIsNone(audit_schema.find_audit_report(novel, 99))


class PassportStatusTest(unittest.TestCase):
    def test_normalize_status(self):
        self.assertEqual(normalize_status("PASS"), "pass")
        self.assertEqual(normalize_status(True), "pass")
        self.assertEqual(normalize_status("failed"), "fail")
        self.assertEqual(normalize_status(False), "fail")
        self.assertEqual(normalize_status(None), "pending")


class ChapterWorkflowTest(unittest.TestCase):
    def test_transition_preserves_completed_stage_and_counts_attempts(self):
        workflow = transition(init_workflow(), "pre", "pass", next_action="write_then_post")
        workflow = transition(workflow, "draft", "pending", next_action="post --phase audit")
        self.assertEqual(workflow["last_completed_stage"], "pre")
        self.assertEqual(workflow["stage"], "draft")
        self.assertEqual(workflow["status"], "pending")
        self.assertEqual(workflow["attempts"], {"pre": 1, "draft": 1})

    def test_lock_blocks_reentrant_processing_and_cleans_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = Path(tmp) / "书"
            with chapter_lock(novel, 3):
                with self.assertRaises(RuntimeError):
                    with chapter_lock(novel, 3):
                        pass
            self.assertFalse((novel / "素材" / "runs" / "chapter_003.lock").exists())


class PlatformProfileTest(unittest.TestCase):
    def test_target_platform_alias_wins_for_short_story_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = Path(tmp) / "短篇小说" / "001_故事"
            novel.mkdir(parents=True)
            (novel / "novel_state.json").write_text(
                json.dumps({"platform": "短篇小说", "target_platform": "知乎盐选"}, ensure_ascii=False),
                encoding="utf-8",
            )
            self.assertEqual(platform_for_novel_dir(novel), "知乎")
            profile = load_platform_profile(novel, project_root=PROJECT_ROOT)
            self.assertEqual(profile["platform"], "知乎")
            self.assertEqual(evaluate_word_count(4000, profile)["status"], "pass")


class StoryIndexTest(unittest.TestCase):
    def test_sync_builds_queryable_read_model_and_reconciles_deletions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            novel = root / "novel_output" / "番茄" / "测试书"
            chapter = novel / "正文" / "第001章-开端.md"
            state = novel / "novel_state.json"
            chapter.parent.mkdir(parents=True)
            chapter.write_text("这是第一章。" * 100, encoding="utf-8")
            state.write_text(
                json.dumps(
                    {
                        "title": "测试书",
                        "platform": "番茄",
                        "current_chapter": 1,
                        "last_completed_chapter": 0,
                        "updated_at": "2026-11-10T00:00:00",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            first = sync_root_index(root)
            self.assertEqual(first["projects"], 1)
            self.assertTrue(index_path(root).is_file())
            projects = query_projects(index_path(root))
            self.assertEqual(projects[0]["title"], "测试书")
            rows = query_chapters(index_path(root), project_key(root, novel))
            self.assertEqual(rows[0]["word_count"], 500)

            chapter.unlink()
            second = sync_root_index(root)
            self.assertEqual(second["chapters"], 0)
            self.assertEqual(query_chapters(index_path(root), project_key(root, novel)), [])


class RevisionControlTest(unittest.TestCase):
    def test_proposal_requires_approval_and_snapshot_restores_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = Path(tmp) / "书"
            chapter = novel / "正文" / "第001章-开端.md"
            chapter.parent.mkdir(parents=True)
            chapter.write_text("旧正文", encoding="utf-8")
            original = create_snapshot(novel, 1, reason="测试快照", source="test")
            proposal = create_proposal(novel, 1, "新正文", reason="测试修改", source="test")
            self.assertEqual(chapter.read_text(encoding="utf-8"), "旧正文")

            rejected = review_proposal(novel, 1, proposal["proposal_id"], approve=False)
            self.assertEqual(rejected["status"], "rejected")
            approved = create_proposal(novel, 1, "新正文", reason="测试批准", source="test")
            applied = review_proposal(novel, 1, approved["proposal_id"], approve=True)
            self.assertEqual(applied["status"], "approved")
            self.assertEqual(chapter.read_text(encoding="utf-8"), "新正文")

            restored = restore_snapshot(novel, 1, original["snapshot_id"])
            self.assertEqual(restored["snapshot_id"], original["snapshot_id"])
            self.assertEqual(chapter.read_text(encoding="utf-8"), "旧正文")

    def test_stale_proposal_cannot_overwrite_new_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = Path(tmp) / "书"
            chapter = novel / "正文" / "第001章-开端.md"
            chapter.parent.mkdir(parents=True)
            chapter.write_text("初稿", encoding="utf-8")
            proposal = create_proposal(novel, 1, "提案稿", reason="测试过期", source="test")
            chapter.write_text("人工新稿", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                review_proposal(novel, 1, proposal["proposal_id"], approve=True)
            self.assertEqual(chapter.read_text(encoding="utf-8"), "人工新稿")


class ScenePassportTest(unittest.TestCase):
    def test_scene_plan_progress_is_reflected_in_chapter_passport(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = Path(tmp) / "书"
            (novel / "正文").mkdir(parents=True)
            (novel / "正文" / "第001章-开端.md").write_text("正文", encoding="utf-8")
            summary = initialize_scene_plan(
                novel,
                1,
                [
                    {"title": "冲突", "goal": "建立冲突"},
                    {"title": "反转", "hook": "留下反转"},
                ],
            )
            self.assertEqual(summary["status"], "pending")
            self.assertEqual(len(list_scene_passports(novel, 1)), 2)
            transition_scene(novel, 1, 1, "pass")
            transition_scene(novel, 1, 2, "pass")
            final = json.loads((novel / "摘要" / "chapter_001_passport.json").read_text(encoding="utf-8"))
            self.assertTrue(final["scene_index"]["enabled"])
            self.assertEqual(final["scene_index"]["status"], "pass")


class QualityProfileTest(unittest.TestCase):
    def test_quality_mode_reads_project_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = Path(tmp) / "书"
            novel.mkdir(parents=True)
            (novel / "novel_state.json").write_text(
                json.dumps({"quality_mode": "tribunal"}, ensure_ascii=False),
                encoding="utf-8",
            )
            mode, profile = quality_profile(novel)
            self.assertEqual(mode, "tribunal")
            self.assertTrue(profile["requires_quality_review"])


class RetrievalAndContractTest(unittest.TestCase):
    def test_knowledge_index_searches_rebuildable_read_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc = root / "knowledge_base" / "40_Writing" / "张力技法.md"
            doc.parent.mkdir(parents=True)
            doc.write_text("# 潜台词与张力\n对话需要阻力和节奏。", encoding="utf-8")
            result = sync_knowledge_index(root)
            self.assertEqual(result["documents"], 1)
            hits = search_knowledge(root, "张力 对话")
            self.assertEqual(hits[0]["path"], "knowledge_base/40_Writing/张力技法.md")
            vector_hits = search_knowledge(root, "张力 对话", backend="tfidf")
            self.assertEqual(vector_hits[0]["path"], "knowledge_base/40_Writing/张力技法.md")

    def test_tension_contract_requires_peak_and_release(self):
        report = validate_tension_curve(
            {"chapter": 1, "chapter_metrics": {"tension_curve": [2, 4, 5]}},
            {"enabled": True, "min_points": 3, "min_peak": 7, "require_release": True},
        )
        self.assertEqual(report["status"], "fail")
        self.assertTrue(any("峰值" in error for error in report["errors"]))

    def test_heuristic_tension_estimate_is_explicitly_non_editorial(self):
        report = estimate_tension_curve("平静的夜晚。\n\n危险逼近！他转身逃跑。", chapter=2)
        self.assertEqual(report["status"], "estimated")
        self.assertTrue(report["estimated"])
        self.assertEqual(report["source"], "heuristic")
        self.assertTrue(report["points"])

    def test_contract_validators_report_shape_errors(self):
        summary = validate_chapter_summary({"chapter": 1, "key_events": {}}, chapter=1, strict=True)
        state = validate_project_state({"chapters": []})
        self.assertEqual(summary["status"], "fail")
        self.assertEqual(state["status"], "fail")


class ChapterCommitTest(unittest.TestCase):
    def test_commit_binds_artifacts_and_detects_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = Path(tmp) / "书"
            chapter_file = novel / "正文" / "第001章-开始.md"
            passport_file = novel / "摘要" / "chapter_001_passport.json"
            audit_file = novel / "素材" / "audit_ch001.json"
            delta_file = novel / "摘要" / "chapter_001_truth_delta.json"
            for path, content in [
                (chapter_file, "正文内容"),
                (passport_file, "{\"pipeline_result\": \"pass\"}"),
                (audit_file, "{\"status\": \"pass\"}"),
                (delta_file, "{\"chapter\": 1}"),
            ]:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            record_chapter_commit(
                novel,
                1,
                chapter_file=chapter_file,
                artifacts={
                    "chapter": chapter_file,
                    "passport": passport_file,
                    "audit": audit_file,
                    "truth_delta": delta_file,
                    "optional_report": None,
                },
            )
            ok, detail = verify_chapter_commit(novel, 1)
            self.assertTrue(ok, detail)

            chapter_file.write_text("正文被改写", encoding="utf-8")
            ok, detail = verify_chapter_commit(novel, 1)
            self.assertFalse(ok)
            self.assertIn("chapter", detail)

    def test_commit_rejects_missing_required_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = Path(tmp) / "书"
            chapter_file = novel / "正文" / "第001章-开始.md"
            chapter_file.parent.mkdir(parents=True)
            chapter_file.write_text("正文内容", encoding="utf-8")

            with self.assertRaises(FileNotFoundError):
                record_chapter_commit(
                    novel,
                    1,
                    chapter_file=chapter_file,
                    artifacts={"chapter": chapter_file, "audit": novel / "素材" / "missing.json"},
                )


class RunLedgerTest(unittest.TestCase):
    def test_run_context_and_durable_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = Path(tmp) / "书"
            chapter_file = novel / "正文" / "第003章-回声.md"
            command = ["python", "tool.py", "--chapter-file", str(chapter_file)]
            inferred_novel, chapter = infer_run_context(command)
            self.assertEqual(inferred_novel, novel)
            self.assertEqual(chapter, 3)

            append_run(novel, {"chapter": 3, "description": "审计", "status": "pass"})
            records = load_runs(novel, chapter=3)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["schema_version"], "1.0")


class ProjectStateTest(unittest.TestCase):
    def test_normalize_preserves_legacy_chapters(self):
        state = ensure_state_shape({"chapters": [{"number": 1}], "custom": "keep"}, title="书")
        self.assertEqual(state["schema_version"], "2.0")
        self.assertEqual(state["chapters"], {})
        self.assertEqual(state["chapters_legacy"], [{"number": 1}])
        self.assertEqual(state["custom"], "keep")

    def test_migration_is_backup_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = Path(tmp) / "番茄" / "001_书"
            novel.mkdir(parents=True)
            state_path = novel / "novel_state.json"
            state_path.write_text(json.dumps({"chapters": []}, ensure_ascii=False), encoding="utf-8")

            preview = migrate_state_file(novel)
            self.assertFalse(preview["applied"])
            self.assertIn("schema_version", preview["changed_keys"])
            self.assertEqual(json.loads(state_path.read_text(encoding="utf-8")), {"chapters": []})

            applied = migrate_state_file(novel, apply=True)
            self.assertTrue(applied["applied"])
            self.assertTrue(Path(applied["backup"]).exists())
            migrated = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(migrated["schema_version"], "2.0")
            self.assertEqual(migrated["chapters"], {})
            self.assertEqual(migrated["chapters_legacy"], [])


class ProjectRegistryTest(unittest.TestCase):
    def test_accepted_alias_resolves_id_drift_without_renaming(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "novel_output" / "番茄" / "002_书"
            project = root / "knowledge_base" / "80_Projects" / "003_书"
            output.mkdir(parents=True)
            project.mkdir(parents=True)
            aliases_path = root / "knowledge_base" / "80_Projects" / "_PROJECT_ALIASES.json"
            aliases_path.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "mappings": [
                            {
                                "canonical_title": "书",
                                "canonical_project_id": "002",
                                "status": "accepted",
                                "output_paths": ["novel_output/番茄/002_书"],
                                "project_paths": ["knowledge_base/80_Projects/003_书"],
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            registry = build_registry(root)
            self.assertEqual(registry["summary"]["issue_count"], 0)
            entry = registry["projects"][0]
            self.assertEqual(entry["project_id"], "002")
            self.assertEqual(entry["legacy_project_ids"], ["003"])
            self.assertTrue((output).is_dir())
            self.assertTrue((project).is_dir())

    def test_unmapped_id_drift_remains_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "novel_output" / "番茄" / "002_书").mkdir(parents=True)
            (root / "knowledge_base" / "80_Projects" / "003_书").mkdir(parents=True)
            registry = build_registry(root)
            self.assertEqual(registry["summary"]["issue_count"], 1)
            self.assertEqual(registry["issues"][0]["kind"], "id_mismatch")


class GateTest(unittest.TestCase):
    def _write_state(self, novel: Path, gate: dict) -> None:
        (novel / "素材").mkdir(parents=True, exist_ok=True)
        (novel / "novel_state.json").write_text(
            json.dumps({"workflow_gate": gate}, ensure_ascii=False), encoding="utf-8"
        )

    def test_missing_gate_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = Path(tmp)
            self._write_state(novel, {})
            ok, _ = verify_bootstrap_gate(novel)
            self.assertFalse(ok)

    def test_fingerprint_match_and_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = Path(tmp)
            report = novel / "素材" / "project_bootstrap_gate.json"
            report.parent.mkdir(parents=True)
            report.write_text(json.dumps({"can_write_chapter": True}), encoding="utf-8")
            from novel_creation_promax.core.gate import sha256_file

            self._write_state(
                novel,
                {
                    "can_write_chapter": True,
                    "bootstrap_report": "素材/project_bootstrap_gate.json",
                    "bootstrap_report_sha256": sha256_file(report),
                },
            )
            ok, detail = verify_bootstrap_gate(novel)
            self.assertTrue(ok, detail)

            report.write_text(json.dumps({"can_write_chapter": True, "x": 1}), encoding="utf-8")
            ok, detail = verify_bootstrap_gate(novel)
            self.assertFalse(ok)
            self.assertIn("指纹", detail)

    def test_legacy_gate_without_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel = Path(tmp)
            report = novel / "素材" / "project_bootstrap_gate.json"
            report.parent.mkdir(parents=True)
            report.write_text(json.dumps({"can_write_chapter": True}), encoding="utf-8")
            self._write_state(
                novel,
                {"can_write_chapter": True, "bootstrap_report": "素材/project_bootstrap_gate.json"},
            )
            ok, _ = verify_bootstrap_gate(novel)
            self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
