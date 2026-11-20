#!/usr/bin/env python3
"""Long-term idea library: archive, deduplicate, index and search ideas/research.

Runtime outputs stay in ``创意/`` and ``素材/调研/``. This tool copies finalized
items into a durable workspace library (default ``创意库/``) with stable IDs,
metadata, content hashes and a rebuildable index.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from novel_creation_promax.core.jsonio import load_json, now_iso, save_json  # noqa: E402

LIBRARY_NAME = "创意库"
IDEA_DIR = "创意卡"
RESEARCH_DIR = "调研"
INDEX_JSON = "_INDEX.json"
INDEX_MD = "_INDEX.md"
SCHEMA_FILE = "_SCHEMA.json"
SCHEMA_VERSION = "1.0"
SAFE_NAME = re.compile(r"[^0-9A-Za-z一-鿿_-]+")
SECTION_HEADING = re.compile(r"(?m)^##\s+(\d+)\.\s+(.+)$")
UNSAFE_TITLE = re.compile(r"[\r\n\t]+")


def library_dir(workspace: Path, override: str = "") -> Path:
    if override:
        return Path(override).expanduser().resolve()
    return (workspace / LIBRARY_NAME).resolve()


def init_library(library: Path) -> dict[str, Any]:
    library.mkdir(parents=True, exist_ok=True)
    (library / IDEA_DIR).mkdir(exist_ok=True)
    (library / RESEARCH_DIR).mkdir(exist_ok=True)
    schema_path = library / SCHEMA_FILE
    if not schema_path.exists():
        save_json(
            schema_path,
            {
                "schema_version": SCHEMA_VERSION,
                "description": "长期创意库：创意卡与调研报告的稳定元数据。",
                "idea_fields": ["id", "title", "platform", "genre", "tags", "score", "status", "summary", "source", "archived_at", "content_hash"],
                "research_fields": ["id", "title", "platform", "genre", "tags", "source", "archived_at", "content_hash"],
            },
        )
    index_path = library / INDEX_JSON
    if not index_path.exists():
        save_json(index_path, {"schema_version": SCHEMA_VERSION, "updated_at": now_iso(), "ideas": [], "research": []})
    save_markdown_index(library, load_index(library))
    return {"library": str(library), "schema": str(schema_path)}


def load_index(library: Path) -> dict[str, Any]:
    payload = load_json(library / INDEX_JSON, {})
    if not isinstance(payload, dict):
        payload = {}
    payload.setdefault("schema_version", SCHEMA_VERSION)
    payload.setdefault("updated_at", now_iso())
    payload.setdefault("ideas", [])
    payload.setdefault("research", [])
    return payload


def _normalize_title(value: str) -> str:
    return re.sub(r"\s+", "", value or "").lower()


def _safe_title(value: str) -> str:
    cleaned = SAFE_NAME.sub("-", UNSAFE_TITLE.sub(" ", value or "")).strip("-")
    return (cleaned or "untitled")[:60]


def _frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    meta: dict[str, Any] = {}
    for line in text[4:end].splitlines():
        if ":" not in line or line.startswith((" ", "\t")):
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            meta[key] = [item.strip().strip("'\"") for item in value[1:-1].split(",") if item.strip()]
        else:
            meta[key] = value.strip("'\"")
    return meta, text[end + 4:].lstrip("\n")


def _render_frontmatter(meta: dict[str, Any]) -> str:
    order = ["id", "title", "type", "platform", "genre", "tags", "score", "status", "summary", "source", "archived_at", "content_hash"]
    lines = ["---"]
    for key in order:
        if key not in meta or meta[key] in ("", None, []):
            continue
        value = meta[key]
        if isinstance(value, list):
            value = "[" + ", ".join(str(item) for item in value) + "]"
        lines.append(f"{key}: {value}")
    for key, value in meta.items():
        if key in order or value in ("", None, []):
            continue
        if isinstance(value, list):
            value = "[" + ", ".join(str(item) for item in value) + "]"
        lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines)


def _first_heading(body: str) -> str:
    for line in body.splitlines():
        match = re.match(r"^#\s+(.+)$", line.strip())
        if not match:
            continue
        title = match.group(1).strip()
        title = re.sub(r"^创意卡\s*[·:：]?\s*", "", title).strip()
        if title and title not in {"创意卡", "创意"}:
            return title
    return ""


def _first_paragraph(body: str) -> str:
    lines: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            if lines:
                break
            continue
        if stripped.startswith("#"):
            if lines:
                break
            continue
        lines.append(stripped)
        if len("".join(lines)) >= 200:
            break
    return "".join(lines)[:200]


def _tags_from_text(text: str) -> list[str]:
    match = re.search(r"(?:标签|tags)[:：]\s*(.+)", text, re.IGNORECASE)
    if not match:
        return []
    return [item.strip() for item in re.split(r"[,，、|/;；\s]+", match.group(1)) if item.strip()]


def _platform_from_text(text: str, path: Path) -> str:
    match = re.search(r"(?:平台|platform)[:：]\s*([^\n]+)", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    for platform in ("番茄", "起点", "知乎", "七猫", "晋江", "飞卢", "纵横", "豆瓣"):
        if platform in path.as_posix():
            return platform
    return ""


def _genre_from_text(text: str) -> str:
    match = re.search(r"(?:题材|genre)[:：]\s*([^\n]+)", text, re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _score_from_text(text: str) -> float | None:
    match = re.search(r"(?:总分|score)[:：]?\s*(\d+(?:\.\d+)?)", text, re.IGNORECASE)
    return float(match.group(1)) if match else None


def _hash(text: str) -> str:
    normalized = re.sub(r"\s+", "", text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def split_idea_sections(text: str) -> list[tuple[str, str]]:
    """Split a batch idea card by ``## N. Title`` headings."""
    meta, body = _frontmatter(text)
    del meta
    matches = list(SECTION_HEADING.finditer(body))
    if len(matches) < 2:
        return [(_first_heading(body) or "未命名创意", body.strip())]
    sections: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        title = match.group(2).strip()
        if title in {"排序表", "总览", "目录"}:
            continue
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        sections.append((title, body[start:end].strip()))
    return sections or [(_first_heading(body) or "未命名创意", body.strip())]


def _next_id(entries: list[dict[str, Any]], prefix: str, today: str) -> str:
    same_day = [entry.get("id", "") for entry in entries if str(entry.get("id", "")).startswith(f"{prefix}-{today}-")]
    numbers = []
    for value in same_day:
        match = re.search(r"-(\d{3})$", value)
        if match:
            numbers.append(int(match.group(1)))
    return f"{prefix}-{today}-{max(numbers, default=0) + 1:03d}"


def _find_duplicate(entries: list[dict[str, Any]], content_hash: str, title: str) -> dict[str, Any] | None:
    normalized = _normalize_title(title)
    for entry in entries:
        if entry.get("content_hash") == content_hash:
            return entry
        if normalized and _normalize_title(str(entry.get("title", ""))) == normalized:
            return entry
    return None


def _archive_one(
    library: Path,
    index: dict[str, Any],
    *,
    kind: str,
    title: str,
    body: str,
    platform: str,
    genre: str,
    tags: list[str],
    score: float | None,
    status: str,
    source: str,
) -> dict[str, Any]:
    entries = index["ideas"] if kind == "idea" else index["research"]
    prefix = "IDEA" if kind == "idea" else "RES"
    content_hash = _hash(body)
    duplicate = _find_duplicate(entries, content_hash, title)
    if duplicate:
        return {"status": "duplicate", "id": duplicate.get("id"), "title": duplicate.get("title")}
    today = datetime.now().strftime("%Y%m%d")
    entry_id = _next_id(entries, prefix, today)
    directory = library / (IDEA_DIR if kind == "idea" else RESEARCH_DIR)
    filename = f"{entry_id}_{_safe_title(title)}.md"
    path = directory / filename
    meta = {
        "id": entry_id,
        "title": title,
        "type": kind,
        "platform": platform,
        "genre": genre,
        "tags": tags,
        "score": score,
        "status": status if kind == "idea" else "",
        "summary": _first_paragraph(body),
        "source": source,
        "archived_at": now_iso(),
        "content_hash": content_hash,
    }
    path.write_text(_render_frontmatter(meta) + "\n\n" + body.strip() + "\n", encoding="utf-8")
    entry = {
        **meta,
        "path": str(path.relative_to(library)),
    }
    entries.append(entry)
    index["updated_at"] = now_iso()
    save_json(library / INDEX_JSON, index)
    save_markdown_index(library, index)
    return {"status": "archived", "id": entry_id, "title": title, "path": str(path)}


def save_markdown_index(library: Path, index: dict[str, Any]) -> None:
    lines = [
        "# 创意库索引",
        "",
        "> 自动生成，禁止手改；用 `tools/idea_library.py rebuild-index` 重建。",
        "",
        f"> 更新时间：{index.get('updated_at', '')}",
        "",
        "## 创意卡",
        "",
        "| ID | 标题 | 平台 | 题材 | 总分 | 状态 | 文件 |",
        "|---|---|---|---|---|---|---|",
    ]
    for entry in sorted(index.get("ideas", []), key=lambda item: str(item.get("id", ""))):
        lines.append(
            "| {id} | {title} | {platform} | {genre} | {score} | {status} | {path} |".format(
                id=entry.get("id", ""),
                title=entry.get("title", ""),
                platform=entry.get("platform", ""),
                genre=entry.get("genre", ""),
                score=entry.get("score", ""),
                status=entry.get("status", ""),
                path=entry.get("path", ""),
            )
        )
    lines.extend(["", "## 调研", "", "| ID | 标题 | 平台 | 题材 | 文件 |", "|---|---|---|---|---|"])
    for entry in sorted(index.get("research", []), key=lambda item: str(item.get("id", ""))):
        lines.append(
            "| {id} | {title} | {platform} | {genre} | {path} |".format(
                id=entry.get("id", ""),
                title=entry.get("title", ""),
                platform=entry.get("platform", ""),
                genre=entry.get("genre", ""),
                path=entry.get("path", ""),
            )
        )
    (library / INDEX_MD).write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def archive_file(
    workspace: Path,
    source: Path,
    *,
    kind: str,
    library_override: str = "",
    title: str = "",
    platform: str = "",
    genre: str = "",
    tags: list[str] | None = None,
    score: float | None = None,
    status: str = "candidate",
    split: bool = False,
) -> dict[str, Any]:
    library = library_dir(workspace, library_override)
    init_library(library)
    index = load_index(library)
    text = source.read_text(encoding="utf-8", errors="replace")
    meta, body = _frontmatter(text)
    default_title = title or str(meta.get("title") or "") or _first_heading(body) or source.stem
    default_platform = platform or str(meta.get("platform") or "") or _platform_from_text(text, source)
    default_genre = genre or str(meta.get("genre") or "") or _genre_from_text(text)
    default_tags = tags or (meta.get("tags") if isinstance(meta.get("tags"), list) else _tags_from_text(text))
    default_score = score if score is not None else (meta.get("score") if meta.get("score") not in (None, "") else _score_from_text(text))
    try:
        default_score = float(default_score) if default_score not in (None, "") else None
    except (TypeError, ValueError):
        default_score = None

    results: list[dict[str, Any]] = []
    if kind == "idea" and split:
        for section_title, section_body in split_idea_sections(text):
            section_score = _score_from_text(section_body)
            results.append(
                _archive_one(
                    library, index,
                    kind="idea",
                    title=section_title,
                    body=section_body,
                    platform=default_platform or _platform_from_text(section_body, source),
                    genre=default_genre or _genre_from_text(section_body),
                    tags=_tags_from_text(section_body) or list(default_tags or []),
                    score=section_score,
                    status=status,
                    source=str(source),
                )
            )
    else:
        results.append(
            _archive_one(
                library, index,
                kind=kind,
                title=default_title,
                body=body.strip(),
                platform=default_platform,
                genre=default_genre,
                tags=list(default_tags or []),
                score=default_score if kind == "idea" else None,
                status=status,
                source=str(source),
            )
        )
    return {"library": str(library), "results": results}


def search(
    workspace: Path,
    query: str,
    *,
    library_override: str = "",
    platform: str = "",
    genre: str = "",
    tag: str = "",
    limit: int = 10,
) -> list[dict[str, Any]]:
    library = library_dir(workspace, library_override)
    index = load_index(library)
    tokens = [token.lower() for token in re.split(r"\s+", query.strip()) if token]
    results: list[dict[str, Any]] = []
    for kind in ("ideas", "research"):
        for entry in index.get(kind, []):
            if platform and platform not in str(entry.get("platform", "")):
                continue
            if genre and genre not in str(entry.get("genre", "")):
                continue
            if tag and tag not in [str(item) for item in entry.get("tags", [])]:
                continue
            haystack = " ".join(
                str(entry.get(key, "")) for key in ("title", "platform", "genre", "summary", "id")
            ) + " " + " ".join(str(item) for item in entry.get("tags", []))
            haystack = haystack.lower()
            score = sum(5 if token in str(entry.get("title", "")).lower() else 2 for token in tokens if token in haystack)
            if tokens and score == 0:
                continue
            results.append({**entry, "kind": "idea" if kind == "ideas" else "research", "match_score": score})
    results.sort(key=lambda item: (-int(item.get("match_score", 0)), str(item.get("id", ""))))
    return results[:limit]


def list_entries(workspace: Path, *, library_override: str = "") -> dict[str, Any]:
    library = library_dir(workspace, library_override)
    index = load_index(library)
    return {"library": str(library), "ideas": index.get("ideas", []), "research": index.get("research", [])}


def rebuild_index(workspace: Path, *, library_override: str = "") -> dict[str, Any]:
    library = library_dir(workspace, library_override)
    init_library(library)
    index = {"schema_version": SCHEMA_VERSION, "updated_at": now_iso(), "ideas": [], "research": []}
    for kind, directory in (("ideas", IDEA_DIR), ("research", RESEARCH_DIR)):
        for path in sorted((library / directory).glob("*.md")):
            meta, body = _frontmatter(path.read_text(encoding="utf-8", errors="replace"))
            entry_id = str(meta.get("id") or path.stem)
            score = meta.get("score")
            try:
                score = float(score) if score not in (None, "") else None
            except (TypeError, ValueError):
                score = None
            index[kind].append(
                {
                    "id": entry_id,
                    "title": str(meta.get("title") or _first_heading(body) or path.stem),
                    "type": "idea" if kind == "ideas" else "research",
                    "platform": str(meta.get("platform") or ""),
                    "genre": str(meta.get("genre") or ""),
                    "tags": meta.get("tags") if isinstance(meta.get("tags"), list) else [],
                    "score": score,
                    "status": meta.get("status") or "",
                    "summary": str(meta.get("summary") or _first_paragraph(body)),
                    "source": str(meta.get("source") or ""),
                    "archived_at": str(meta.get("archived_at") or ""),
                    "content_hash": str(meta.get("content_hash") or ""),
                    "path": str(path.relative_to(library)),
                }
            )
    save_json(library / INDEX_JSON, index)
    save_markdown_index(library, index)
    return {"library": str(library), "ideas": len(index["ideas"]), "research": len(index["research"])}


def main() -> int:
    parser = argparse.ArgumentParser(description="长期创意库：归档、查重、索引与搜索")
    parser.add_argument("--workspace", default=str(Path.cwd()), help="工作区根目录")
    parser.add_argument("--library-dir", default="", help="自定义创意库目录；默认 {workspace}/创意库")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="初始化创意库")
    init.set_defaults(func=lambda args: print(json.dumps(init_library(library_dir(Path(args.workspace), args.library_dir)), ensure_ascii=False, indent=2)) or 0)

    archive_idea = sub.add_parser("archive-idea", help="归档创意卡")
    archive_idea.add_argument("--file", required=True)
    archive_idea.add_argument("--title", default="")
    archive_idea.add_argument("--platform", default="")
    archive_idea.add_argument("--genre", default="")
    archive_idea.add_argument("--tags", nargs="*", default=None)
    archive_idea.add_argument("--score", type=float, default=None)
    archive_idea.add_argument("--status", default="candidate")
    archive_idea.add_argument("--split", action="store_true", help="按 ## N. 标题拆成多个创意")
    archive_idea.set_defaults(
        func=lambda args: print(json.dumps(archive_file(
            Path(args.workspace), Path(args.file), kind="idea",
            library_override=args.library_dir, title=args.title, platform=args.platform,
            genre=args.genre, tags=args.tags, score=args.score, status=args.status, split=args.split,
        ), ensure_ascii=False, indent=2)) or 0
    )

    archive_research = sub.add_parser("archive-research", help="归档调研报告")
    archive_research.add_argument("--file", required=True)
    archive_research.add_argument("--title", default="")
    archive_research.add_argument("--platform", default="")
    archive_research.add_argument("--genre", default="")
    archive_research.add_argument("--tags", nargs="*", default=None)
    archive_research.set_defaults(
        func=lambda args: print(json.dumps(archive_file(
            Path(args.workspace), Path(args.file), kind="research",
            library_override=args.library_dir, title=args.title, platform=args.platform,
            genre=args.genre, tags=args.tags,
        ), ensure_ascii=False, indent=2)) or 0
    )

    search_parser = sub.add_parser("search", help="搜索创意库")
    search_parser.add_argument("--query", default="")
    search_parser.add_argument("--platform", default="")
    search_parser.add_argument("--genre", default="")
    search_parser.add_argument("--tag", default="")
    search_parser.add_argument("--limit", type=int, default=10)
    search_parser.add_argument("--json", action="store_true")
    search_parser.set_defaults(
        func=lambda args: print(json.dumps(search(
            Path(args.workspace), args.query, library_override=args.library_dir,
            platform=args.platform, genre=args.genre, tag=args.tag, limit=args.limit,
        ), ensure_ascii=False, indent=2) if args.json else "\n".join(
            f"{item['id']} | {item['title']} | {item.get('platform','')} | {item.get('genre','')}"
            for item in search(
                Path(args.workspace), args.query, library_override=args.library_dir,
                platform=args.platform, genre=args.genre, tag=args.tag, limit=args.limit,
            )
        )) or 0
    )

    list_parser = sub.add_parser("list", help="列出创意库")
    list_parser.add_argument("--json", action="store_true")
    list_parser.set_defaults(
        func=lambda args: print(json.dumps(list_entries(Path(args.workspace), library_override=args.library_dir), ensure_ascii=False, indent=2)) or 0
    )

    rebuild = sub.add_parser("rebuild-index", help="从文件重建索引")
    rebuild.set_defaults(
        func=lambda args: print(json.dumps(rebuild_index(Path(args.workspace), library_override=args.library_dir), ensure_ascii=False, indent=2)) or 0
    )

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
