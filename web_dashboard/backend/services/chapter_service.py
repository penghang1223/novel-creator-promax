"""Read/write chapter .md files and summaries."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional

from config import PROJECT_ROOT

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from models.chapter import ChapterContent, ChapterSummary
from novel_creation_promax.core.jsonio import load_json, now_iso, save_json
from novel_creation_promax.core.passport import load_passport, save_passport
from novel_creation_promax.core.revision_control import create_snapshot
from novel_creation_promax.core.chapter_commit import remove_chapter_commit
from novel_creation_promax.core.chapter_workflow import transition
from utils.paths import (
    count_chinese_chars,
    extract_chapter_title,
    find_chapter_file,
    get_novel_dir,
    get_summaries_dir,
    list_chapter_files,
)

DIRTY_PIPELINE_STAGES = (
    "pre_write_check",
    "writing_gate",
    "post_write_audit",
    "normalizer",
    "truth_delta",
    "truth_sync",
    "memory_sync",
)


class ChapterService:
    """Service for reading and writing chapter files."""

    def get_chapter_content(self, platform: str, novel_name: str, ch_num: int) -> Optional[ChapterContent]:
        novel_dir = get_novel_dir(platform, novel_name)
        ch_file = find_chapter_file(novel_dir, ch_num)
        if not ch_file:
            return None

        content = ch_file.read_text(encoding="utf-8")
        return ChapterContent(
            chapter_number=ch_num,
            title=extract_chapter_title(ch_file.name),
            content=content,
            word_count=count_chinese_chars(content),
        )

    def save_chapter_content(self, platform: str, novel_name: str, ch_num: int, content: str) -> bool:
        novel_dir = get_novel_dir(platform, novel_name)
        ch_file = find_chapter_file(novel_dir, ch_num)
        if not ch_file:
            return False

        create_snapshot(
            novel_dir,
            ch_num,
            reason="Dashboard 直接编辑前快照",
            source="dashboard",
        )
        ch_file.write_text(content, encoding="utf-8")
        title = extract_chapter_title(ch_file.name)
        passport = load_passport(novel_dir, ch_num, title, ch_file)
        passport["pipeline_result"] = "pending"
        for stage in DIRTY_PIPELINE_STAGES:
            passport["pipeline"][stage] = "pending"
        passport["workflow"] = transition(
            passport.get("workflow", {}),
            "draft",
            "pending",
            next_action="post --phase audit",
            error="Dashboard 直接编辑后需要重新审计",
        )
        passport["inputs"]["dashboard_edit"] = "direct-edit"
        save_passport(novel_dir, ch_num, passport)
        remove_chapter_commit(novel_dir, ch_num)

        state_path = novel_dir / "novel_state.json"
        state = load_json(state_path, None)
        if isinstance(state, dict):
            edit_status = state.setdefault("chapter_edit_status", {})
            if isinstance(edit_status, dict):
                edit_status[f"{ch_num:03d}"] = {
                    "status": "dirty",
                    "source": "dashboard",
                    "updated_at": now_iso(),
                }
            state["resume_point"] = {
                "action": "post",
                "chapter": ch_num,
                "next_chapter": ch_num,
                "hint": f"第{ch_num}章被 Dashboard 修改，必须重新运行 post",
                "updated_at": now_iso(),
            }
            state["updated_at"] = now_iso()
            save_json(state_path, state)
        return True

    def get_chapter_summary(self, platform: str, novel_name: str, ch_num: int) -> dict[str, Any]:
        summary_dir = get_summaries_dir(platform, novel_name)
        summary_path = summary_dir / f"chapter_{ch_num:03d}_summary.json"
        if summary_path.exists():
            with open(summary_path, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        return {}

    def save_chapter_summary(self, platform: str, novel_name: str, ch_num: int, data: dict[str, Any]) -> bool:
        summary_dir = get_summaries_dir(platform, novel_name)
        summary_dir.mkdir(parents=True, exist_ok=True)
        summary_path = summary_dir / f"chapter_{ch_num:03d}_summary.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True

    def list_chapter_files(self, platform: str, novel_name: str) -> list[tuple[int, str, Path]]:
        """List all chapter files with (number, title, path)."""
        result = []
        for num, ch_file in list_chapter_files(get_novel_dir(platform, novel_name)):
            result.append((num, extract_chapter_title(ch_file.name), ch_file))
        return result
