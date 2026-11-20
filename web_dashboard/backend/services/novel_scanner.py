"""Scan novel_output/ to build Kanban board state."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
import re
from typing import Any, Optional

from config import OUTPUT_DIR, PROJECT_ROOT

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from novel_creation_promax.core.jsonio import load_json
from novel_creation_promax.core.passport import passport_path, status_passed
from novel_creation_promax.core.story_index import (
    index_path,
    project_key,
    query_chapters,
    query_projects,
    sync_root_index,
)
from models.novel import (
    ChapterCard,
    NovelListItem,
    NovelOverview,
    PipelineStage,
    StageAsset,
    STAGE_ORDER,
)
from utils.paths import (
    count_chinese_chars,
    extract_chapter_number,
    extract_chapter_title,
    get_novel_state_path,
    get_summaries_dir,
    list_chapter_files,
)


def load_json_safe(path: Path) -> dict[str, Any]:
    data = load_json(path, {})
    return data if isinstance(data, dict) else {}


def _stringify_items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        if isinstance(item, dict):
            item_value = item.get("description") or item.get("content") or item.get("title") or item.get("id")
            result.append(str(item_value if item_value is not None else item))
        else:
            result.append(str(item))
    return result


class NovelScanner:
    """Read the filesystem to build Kanban board state."""

    GENRE_TAG_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("言情", ("言情", "女频", "现言", "古言", "甜宠", "爱情", "恋爱")),
        ("玄幻", ("玄幻", "修仙", "仙侠", "异界")),
        ("都市", ("都市", "职场")),
        ("悬疑", ("悬疑", "推理", "刑侦", "怪谈")),
        ("惊悚", ("惊悚", "恐怖", "灵异")),
        ("科幻", ("科幻", "赛博", "未来")),
        ("游戏", ("游戏", "网游", "电竞")),
        ("历史", ("历史", "古代")),
        ("穿越", ("穿越", "重生")),
        ("末世", ("末世", "灾变")),
        ("系统", ("系统", "系统流")),
        ("异能", ("异能", "超能力")),
        ("脑洞", ("脑洞", "迪化")),
        ("治愈", ("治愈", "疗愈")),
    )

    STAGE_ASSET_PATHS: dict[PipelineStage, tuple[str, ...]] = {
        PipelineStage.IDEA: ("创意", "项目章程.md"),
        PipelineStage.SETTING: ("设定", "小说信息.md"),
        PipelineStage.OUTLINE: ("大纲", "outline.md", "结构"),
        PipelineStage.DETAIL_OUTLINE: ("细纲",),
        PipelineStage.MEMORY: ("记忆",),
        PipelineStage.REVIEW: ("复盘", "review", "完结复盘"),
    }

    def _stage_assets(self, novel_dir: Path) -> dict[PipelineStage, list[StageAsset]]:
        assets = {stage: [] for stage in STAGE_ORDER}
        for stage, candidates in self.STAGE_ASSET_PATHS.items():
            seen: set[str] = set()
            for candidate in candidates:
                target = novel_dir / candidate
                if target.is_file():
                    paths = [target]
                elif target.is_dir():
                    paths = [path for path in sorted(target.rglob("*")) if path.is_file()]
                else:
                    paths = []
                for path in paths:
                    relative_path = path.relative_to(novel_dir).as_posix()
                    if relative_path in seen or any(part.startswith(".") for part in path.relative_to(novel_dir).parts):
                        continue
                    seen.add(relative_path)
                    try:
                        updated_at = datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
                    except OSError:
                        updated_at = None
                    assets[stage].append(
                        StageAsset(
                            name=path.name,
                            path=relative_path,
                            updated_at=updated_at,
                        )
                    )
        return assets

    def _read_genre(self, novel_dir: Path, state: dict[str, Any]) -> str:
        state_genre = str(state.get("genre") or "").strip()
        if state_genre and state_genre not in {"待填写", "未填写", "未知"}:
            return state_genre
        for relative_path in ("项目章程.md", "小说信息.md", "素材/小说信息.md"):
            path = novel_dir / relative_path
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            match = re.search(r"(?:题材|类型)\s*[：:]\s*([^\n\r]+)", text)
            if match:
                genre = match.group(1).strip().strip("`* ")
                if genre and genre not in {"待填写", "未填写", "未知"}:
                    return genre
        return ""

    def _genre_tags(self, genre: str) -> list[str]:
        normalized = genre.lower()
        tags = [
            label
            for label, patterns in self.GENRE_TAG_RULES
            if any(pattern.lower() in normalized for pattern in patterns)
        ]
        return tags or ["未分类"]

    def _length_type(self, platform: str, novel_name: str, state: dict[str, Any], chapters_written: int) -> str:
        planned = state.get("total_chapters_planned")
        if isinstance(planned, (int, float)) and planned > 0:
            chapter_count = int(planned)
        elif chapters_written > 0:
            chapter_count = chapters_written
        elif "短篇" in platform or "短篇" in novel_name:
            return "短篇"
        else:
            return "未分类"

        if chapter_count <= 50:
            return "短篇"
        if chapter_count <= 100:
            return "中篇"
        return "长篇"

    def _novel_classification(
        self, novel_dir: Path, state: dict[str, Any], chapters_written: int
    ) -> tuple[str, str, list[str]]:
        genre = self._read_genre(novel_dir, state)
        length_type = self._length_type(novel_dir.parent.name, novel_dir.name, state, chapters_written)
        return length_type, genre, self._genre_tags(genre)

    def _indexed_projects(self) -> list[dict[str, Any]]:
        try:
            sync_root_index(PROJECT_ROOT, output_root=OUTPUT_DIR)
            return query_projects(index_path(PROJECT_ROOT))
        except (OSError, RuntimeError):
            return []

    def list_novels(self) -> list[NovelListItem]:
        """Scan all platforms and novels."""
        indexed_projects = self._indexed_projects()
        if indexed_projects:
            novels = []
            for row in indexed_projects:
                novel_dir = PROJECT_ROOT / row["novel_dir"]
                platform = novel_dir.parent.name
                novel_name = novel_dir.name
                state = load_json_safe(novel_dir / "novel_state.json")
                chapters_written = int(row.get("chapter_count", 0) or 0)
                length_type, genre, genre_tags = self._novel_classification(novel_dir, state, chapters_written)
                novels.append(
                    NovelListItem(
                        novel_name=novel_name,
                        platform=platform,
                        chapters_written=chapters_written,
                        current_stage=self._infer_current_stage(platform, novel_name, state),
                        length_type=length_type,
                        genre=genre,
                        genre_tags=genre_tags,
                        last_updated=row.get("state_updated_at") or state.get("updated_at"),
                    )
                )
            return novels

        novels = []
        if not OUTPUT_DIR.exists():
            return novels

        for platform_dir in sorted(OUTPUT_DIR.iterdir()):
            if not platform_dir.is_dir() or platform_dir.name.startswith("."):
                continue
            platform = platform_dir.name
            for novel_dir in sorted(platform_dir.iterdir()):
                if not novel_dir.is_dir() or novel_dir.name.startswith("."):
                    continue
                state = load_json_safe(get_novel_state_path(platform, novel_dir.name))
                chapters_written = state.get("chapters_written", 0)
                # Count actual chapter files
                chapters_written = max(chapters_written, len(list_chapter_files(novel_dir)))
                length_type, genre, genre_tags = self._novel_classification(novel_dir, state, chapters_written)

                novels.append(
                    NovelListItem(
                        novel_name=novel_dir.name,
                        platform=platform,
                        chapters_written=chapters_written,
                        current_stage=self._infer_current_stage(platform, novel_dir.name, state),
                        length_type=length_type,
                        genre=genre,
                        genre_tags=genre_tags,
                        last_updated=state.get("updated_at"),
                    )
                )
        return novels

    def scan_novel(self, platform: str, novel_name: str) -> NovelOverview:
        """Build full Kanban state for one novel."""
        state = load_json_safe(get_novel_state_path(platform, novel_name))
        chapters = []
        novel_dir = get_novel_state_path(platform, novel_name).parent
        indexed_by_chapter = {}
        try:
            sync_root_index(PROJECT_ROOT, output_root=OUTPUT_DIR)
            indexed_by_chapter = {
                row["chapter_number"]: row
                for row in query_chapters(index_path(PROJECT_ROOT), project_key(PROJECT_ROOT, novel_dir))
            }
        except (OSError, RuntimeError):
            indexed_by_chapter = {}
        for ch_num, ch_file in list_chapter_files(novel_dir):
            card = self._build_chapter_card(
                platform,
                novel_name,
                ch_num,
                ch_file,
                state,
                indexed=indexed_by_chapter.get(ch_num),
            )
            chapters.append(card)

        chapters_written = len(chapters)
        stage_assets = self._stage_assets(novel_dir)
        protagonist = {}
        char_tracking = state.get("character_tracking", {})
        if char_tracking:
            for name, info in char_tracking.items():
                if info.get("role") == "protagonist" or info.get("role") == "main":
                    protagonist = {"name": name, **info}
                    break

        return NovelOverview(
            novel_name=novel_name,
            platform=platform,
            total_chapters_planned=state.get("total_chapters_planned", 0),
            chapters_written=chapters_written,
            current_stage=self._infer_current_stage(platform, novel_name, state),
            chapters=chapters,
            stage_assets=stage_assets,
            protagonist=protagonist,
            last_updated=state.get("updated_at"),
        )

    def _build_chapter_card(
        self,
        platform: str,
        novel_name: str,
        ch_num: int,
        ch_file: Path,
        state: dict,
        indexed: dict[str, Any] | None = None,
    ) -> ChapterCard:
        """Build a ChapterCard from filesystem state."""
        title = extract_chapter_title(ch_file.name)
        if indexed and indexed.get("word_count") is not None:
            word_count = int(indexed["word_count"] or 0)
        else:
            content = ch_file.read_text(encoding="utf-8")
            word_count = count_chinese_chars(content)

        # Load summary
        summary_dir = get_summaries_dir(platform, novel_name)
        summary_path = summary_dir / f"chapter_{ch_num:03d}_summary.json"
        summary = load_json_safe(summary_path)
        passport = load_json_safe(passport_path(get_novel_state_path(platform, novel_name).parent, ch_num))

        # Determine stage and sub-stages
        stage, sub_stages = self._determine_stage(ch_num, state, summary, summary_path, passport)

        # Rhythm type from rhythm_dashboard
        rhythm_dashboard = state.get("rhythm_dashboard", [])
        rhythm_type = None
        if ch_num - 1 < len(rhythm_dashboard):
            rhythm_type = rhythm_dashboard[ch_num - 1].get("type")

        pipeline = passport.get("pipeline", {}) if isinstance(passport, dict) else {}
        audit_passed = status_passed(pipeline.get("post_write_audit")) if pipeline else summary.get("audit_passed")
        gate_passed = status_passed(pipeline.get("writing_gate")) if pipeline else summary.get("gate_passed")

        return ChapterCard(
            chapter_number=ch_num,
            title=title,
            stage=stage,
            rhythm_type=rhythm_type,
            word_count=word_count,
            audit_passed=audit_passed,
            gate_passed=gate_passed,
            last_updated=summary.get("generated_at"),
            sub_stages=sub_stages,
            foreshadowing_planted=_stringify_items(summary.get("foreshadowing_planted", [])),
            foreshadowing_resolved=_stringify_items(summary.get("foreshadowing_resolved", [])),
        )

    def _determine_stage(
        self,
        ch_num: int,
        state: dict,
        summary: dict,
        summary_path: Path,
        passport: dict | None = None,
    ) -> tuple[PipelineStage, dict[str, bool]]:
        """Infer which pipeline stage a chapter is in."""
        has_summary = summary_path.exists() and summary
        has_content = True  # if we found the file, it has content
        pipeline = passport.get("pipeline", {}) if isinstance(passport, dict) else {}
        gate_passed = status_passed(pipeline.get("writing_gate")) if pipeline else summary.get("gate_passed", False)
        audit_passed = status_passed(pipeline.get("post_write_audit")) if pipeline else summary.get("audit_passed", False)
        memory_synced = status_passed(pipeline.get("memory_sync")) if pipeline else summary.get("memory_synced", False)

        sub_stages = {
            "knowledge_pack": status_passed(pipeline.get("knowledge_pack")) if pipeline else False,
            "pre_write": status_passed(pipeline.get("pre_write_check")) if pipeline else summary.get("pre_write_score", 0) >= 70,
            "pass1": has_content,
            "gate": gate_passed,
            "pass2": gate_passed,  # implied if gate passed
            "audit": audit_passed,
            "truth": status_passed(pipeline.get("truth_delta")) if pipeline else False,
            "style": status_passed(pipeline.get("style_calibration")) if pipeline else summary.get("style_checked", False),
            "character": status_passed(pipeline.get("character_consistency")) if pipeline else summary.get("character_checked", False),
            "memory_sync": memory_synced,
        }

        if memory_synced:
            return PipelineStage.MEMORY, sub_stages
        elif audit_passed:
            return PipelineStage.MEMORY, sub_stages
        elif gate_passed:
            return PipelineStage.WRITING, sub_stages
        elif has_content:
            return PipelineStage.WRITING, sub_stages
        elif has_summary:
            return PipelineStage.DETAIL_OUTLINE, sub_stages
        else:
            # No summary, check if this is the next chapter to write
            chapters_written = state.get("chapters_written", 0)
            if ch_num <= chapters_written:
                return PipelineStage.DETAIL_OUTLINE, sub_stages
            return PipelineStage.DETAIL_OUTLINE, sub_stages

    def _infer_current_stage(
        self, platform: str, novel_name: str, state: dict
    ) -> PipelineStage:
        """Infer the novel's overall current stage."""
        ch_count = 0
        novel_dir = get_novel_state_path(platform, novel_name).parent
        ch_count = len(list_chapter_files(novel_dir))

        if ch_count == 0:
            # No chapters written, check what stage we're at
            outline_dir = get_novel_state_path(platform, novel_name).parent / "细纲"
            setting_dir = get_novel_state_path(platform, novel_name).parent / "设定"
            if outline_dir.exists() and any(outline_dir.iterdir()):
                return PipelineStage.DETAIL_OUTLINE
            elif setting_dir.exists() and any(setting_dir.iterdir()):
                return PipelineStage.OUTLINE
            return PipelineStage.IDEA

        # Check latest chapter status
        summary_dir = get_summaries_dir(platform, novel_name)
        latest_summary = load_json_safe(summary_dir / f"chapter_{ch_count:03d}_summary.json")
        latest_passport = load_json_safe(passport_path(novel_dir, ch_count))
        pipeline = latest_passport.get("pipeline", {}) if isinstance(latest_passport, dict) else {}

        if status_passed(pipeline.get("memory_sync")) or latest_summary.get("memory_synced"):
            return PipelineStage.WRITING  # ready for next chapter
        elif status_passed(pipeline.get("post_write_audit")) or latest_summary.get("audit_passed"):
            return PipelineStage.MEMORY
        elif status_passed(pipeline.get("writing_gate")) or latest_summary.get("gate_passed"):
            return PipelineStage.WRITING
        elif latest_summary:
            return PipelineStage.WRITING

        return PipelineStage.WRITING
