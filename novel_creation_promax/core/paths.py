"""Canonical filesystem and chapter path helpers."""

from __future__ import annotations

import re
from pathlib import Path

CHAPTER_EXTENSIONS = {".md", ".txt"}

# 记忆目录历史上有两种命名，读取时都要认。写入统一用 "记忆"。
MEMORY_DIR_ALIASES = ("记忆", "memory")


def _validate_project_component(value: str, label: str) -> str:
    """Validate one user-controlled directory component."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} 不能为空")
    value = value.strip()
    path = Path(value)
    if path.is_absolute() or "/" in value or "\\" in value or any(part in {".", ".."} for part in path.parts):
        raise ValueError(f"{label} 不能包含路径分隔符或路径跳转")
    return value


def count_chinese_chars(text: str) -> int:
    return sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")


def split_project_folder_name(name: str) -> tuple[str | None, str]:
    match = re.match(r"^(?P<id>\d{3})[_\-\s]*(?P<title>.+)$", name.strip())
    if not match:
        return None, name.strip()
    return match.group("id"), match.group("title").strip()


def normalize_title(title: str) -> str:
    value = title.lower()
    value = re.sub(r"[《》【】\[\]（）()_\-\s·:：,，。.!！?？&]+", "", value)
    value = value.replace("已签约完本", "").replace("已签约", "").replace("完本", "")
    return value


def infer_chapter_number(path_or_name: Path | str) -> int | None:
    name = Path(path_or_name).stem
    patterns = [
        r"第0*(\d+)章",
        r"^0*(\d+)[_-]",
        r"chapter_0*(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, name, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def extract_chapter_title(path_or_name: Path | str) -> str:
    name = Path(path_or_name).stem
    name = re.sub(r"^第0*\d+章[-_]?\s*", "", name)
    name = re.sub(r"^0*\d+[-_]\s*", "", name)
    name = re.sub(r"^chapter_0*\d+[-_]?\s*", "", name, flags=re.IGNORECASE)
    return name.strip() or Path(path_or_name).stem


def list_chapter_files(novel_dir: Path) -> list[tuple[int, Path]]:
    """列出全部章节文件。

    递归扫描 ``正文/``，以兼容历史上把章节放进卷子目录的项目
    （例如 ``正文/第一卷/第12章-xxx.md``）。同名章号出现多次时保留
    路径字典序最靠前的一份，避免子目录副本覆盖正式文件。
    """
    body_dir = novel_dir / "正文"
    if not body_dir.exists():
        return []
    items: list[tuple[int, Path]] = []
    seen: dict[int, Path] = {}
    for path in sorted(body_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in CHAPTER_EXTENSIONS:
            continue
        chapter = infer_chapter_number(path)
        if chapter is None:
            continue
        if chapter not in seen:
            seen[chapter] = path
            items.append((chapter, path))
    return sorted(items, key=lambda item: (item[0], item[1].name))


def find_memory_dir(novel_dir: Path) -> Path:
    """返回实际存在的记忆目录；都没有时返回规范名 ``记忆``。"""
    for name in MEMORY_DIR_ALIASES:
        candidate = novel_dir / name
        if candidate.is_dir():
            return candidate
    return novel_dir / "记忆"


def find_chapter_file(novel_dir: Path, chapter: int) -> Path | None:
    for number, path in list_chapter_files(novel_dir):
        if number == chapter:
            return path
    return None


def rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def get_novel_dir(output_dir: Path, platform: str, novel_name: str) -> Path:
    platform = _validate_project_component(platform, "平台")
    novel_name = _validate_project_component(novel_name, "小说目录")
    root = output_dir.resolve()
    novel_dir = output_dir / platform / novel_name
    resolved_novel_dir = novel_dir.resolve()
    try:
        resolved_novel_dir.relative_to(root)
    except ValueError as exc:
        raise ValueError("小说目录必须位于 novel_output 内") from exc
    return novel_dir


def get_chapters_dir(output_dir: Path, platform: str, novel_name: str) -> Path:
    return get_novel_dir(output_dir, platform, novel_name) / "正文"


def get_summaries_dir(output_dir: Path, platform: str, novel_name: str) -> Path:
    return get_novel_dir(output_dir, platform, novel_name) / "摘要"


def get_memory_dir(output_dir: Path, platform: str, novel_name: str) -> Path:
    return find_memory_dir(get_novel_dir(output_dir, platform, novel_name))


def get_novel_state_path(output_dir: Path, platform: str, novel_name: str) -> Path:
    return get_novel_dir(output_dir, platform, novel_name) / "novel_state.json"
