"""Machine-readable knowledge routing and per-chapter pack assembly."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

from .jsonio import load_json, now_iso, save_json
from .knowledge_index import search_knowledge
from .paths import find_chapter_file, rel
from .roots import asset_path, resolve_route_path, workspace_root


# Retrieval is for craft guidance, not project metadata or platform boilerplate.
RETRIEVAL_PREFIXES = (
    "knowledge_base/20_Characters",
    "knowledge_base/30_Plot",
    "knowledge_base/40_Writing",
)

# Routing/index/readme files inside craft directories are still metadata.
RETRIEVAL_EXCLUDE_MARKERS = (
    "_ROUTING",
    "_ROUTES",
    "路由表",
    "索引",
    "README",
    "CLAUDE.md",
    "00_Index",
)

# Selected routes boost their matching craft directories during reranking.
ROUTE_BOOST_PREFIXES = {
    "opening": ("knowledge_base/40_Writing/01_开篇技巧",),
    "engine_opening": ("knowledge_base/40_Writing/01_开篇技巧",),
    "dialogue": ("knowledge_base/40_Writing/03_人物与对话",),
    "high_pressure": ("knowledge_base/40_Writing/04_场景与描写",),
    "intimacy": ("knowledge_base/40_Writing/04_场景与描写",),
    "rhythm": ("knowledge_base/40_Writing/02_节奏与结构",),
    "style_drift": ("knowledge_base/40_Writing/05_降AI痕迹",),
    "engine_deai": ("knowledge_base/40_Writing/05_降AI痕迹",),
    "engine_quality": ("knowledge_base/40_Writing/06_质量校验",),
    "engine_continuity": ("knowledge_base/30_Plot",),
    "engine_craft": ("knowledge_base/20_Characters", "knowledge_base/30_Plot"),
    "short_story": ("knowledge_base/40_Writing/07_短篇与模板",),
}

_CN_DIGITS = "零一二三四五六七八九"


def _cn_number(value: int) -> str:
    if value <= 0:
        return str(value)
    if value < 10:
        return _CN_DIGITS[value]
    if value < 20:
        return "十" + ("" if value == 10 else _CN_DIGITS[value % 10])
    if value < 100:
        tens, ones = divmod(value, 10)
        return _CN_DIGITS[tens] + "十" + ("" if ones == 0 else _CN_DIGITS[ones])
    if value < 1000:
        hundreds, remainder = divmod(value, 100)
        prefix = _CN_DIGITS[hundreds] + "百"
        if remainder == 0:
            return prefix
        if remainder < 10:
            return prefix + "零" + _CN_DIGITS[remainder]
        return prefix + _cn_number(remainder)
    return str(value)


def chapter_outline_text(novel_dir: Path, chapter: int) -> str:
    """Return the outline paragraph for one chapter, if the project has one."""
    candidates: list[Path] = []
    outline_dir = novel_dir / "细纲"
    if outline_dir.is_dir():
        candidates.extend(sorted(outline_dir.glob("*.md")))
    standalone = novel_dir / "outline.md"
    if standalone.is_file():
        candidates.append(standalone)

    markers = (
        f"第{chapter}章",
        f"第{_cn_number(chapter)}章",
        f"第{chapter}节",
        f"第{_cn_number(chapter)}节",
        f"chapter {chapter}",
        f"chapter{chapter}",
    )
    for file in candidates:
        text = file.read_text(encoding="utf-8", errors="replace")
        for marker in markers:
            match = re.search(re.escape(marker), text, re.IGNORECASE)
            if not match:
                continue
            next_chapter = re.search(
                r"第[0-9一二三四五六七八九十百千万零]+[章节]", text[match.end():]
            )
            end = match.end() + next_chapter.start() if next_chapter else len(text)
            return text[match.start():end].strip()[:800]
    return ""


def load_routes(project_root: Path | None = None) -> dict[str, Any]:
    if project_root is not None:
        candidate = project_root / "knowledge_base" / "_ROUTES.json"
        if candidate.is_file():
            return load_json(candidate, {})
    return load_json(asset_path("knowledge_base/_ROUTES.json"), {})


def load_packs(project_root: Path | None = None) -> list[dict[str, Any]]:
    """Load ``knowledge_base/packs/<pack_id>/pack.json`` manifests."""
    root = project_root / "knowledge_base" / "packs" if project_root is not None else None
    if root is None or not root.is_dir():
        root = asset_path("knowledge_base/_ROUTES.json").parent / "packs"
    if not root.is_dir():
        return []
    packs: list[dict[str, Any]] = []
    for path in sorted(root.glob("*/pack.json")):
        payload = load_json(path, {})
        if not isinstance(payload, dict):
            continue
        if str(payload.get("pack_id") or path.parent.name) != path.parent.name:
            continue
        if not isinstance(payload.get("signals"), dict):
            continue
        packs.append(payload)
    return packs


def select_pack(novel_dir: Path, packs: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Pick the pack for a project: explicit ``pack_id`` first, then signals."""
    state = load_json(novel_dir / "novel_state.json", {})
    state = state if isinstance(state, dict) else {}
    explicit = str(state.get("pack_id") or "").strip()
    if explicit:
        return next((pack for pack in packs if str(pack.get("pack_id")) == explicit), None)

    platform = str(state.get("platform") or novel_dir.parent.name).strip()
    genre = infer_genre(novel_dir)
    scored: list[tuple[int, dict[str, Any]]] = []
    for pack in packs:
        signals = pack.get("signals", {})
        score = 3 if signals.get("platform") and signals.get("platform") == platform else 0
        tags = signals.get("genre_tags", [])
        if isinstance(tags, list):
            score += sum(1 for tag in tags if isinstance(tag, str) and tag and tag in genre)
        if score:
            scored.append((score, pack))
    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    best = scored[0][0]
    if best < 3 or sum(1 for score, _ in scored if score == best) != 1:
        return None
    return scored[0][1]


def _pack_selected_routes(
    pack: dict[str, Any],
    selected_keys: set[str],
) -> list[dict[str, Any]]:
    capabilities = set(pack.get("capabilities", []) or [])
    routes = pack.get("routes", {})
    if not isinstance(routes, dict):
        return []
    selected: list[dict[str, Any]] = []
    for key, route in routes.items():
        if not isinstance(route, dict):
            continue
        triggers = set(route.get("trigger_capabilities", []) or [])
        if triggers:
            if not (triggers & capabilities):
                continue
        elif key not in selected_keys:
            continue
        files = [
            {"path": path, "exists": _path_exists(path)}
            for path in route.get("files", [])
            if isinstance(path, str) and path
        ]
        selected.append(
            {
                "key": key,
                "name": route.get("name", key),
                "reason": f"pack:{pack.get('pack_id', '')}",
                "files": files,
                "source": "pack",
            }
        )
    return selected


def _replace_vars(value: str, context: dict[str, Any]) -> str:
    result = value
    for key, item in context.items():
        result = result.replace("{" + key + "}", str(item))
    return result


def _path_exists(path: str, scope: str = "") -> bool:
    if "{" in path or "}" in path:
        return False
    try:
        return resolve_route_path(path, scope=scope).exists()
    except ValueError:
        return False


def infer_genre(novel_dir: Path) -> str:
    state = load_json(novel_dir / "novel_state.json", {})
    if isinstance(state, dict):
        for key in ("genre", "type", "category"):
            value = state.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    bootstrap = load_json(novel_dir / "记忆" / "project_bootstrap.json", {})
    if isinstance(bootstrap, dict):
        for path in (
            ("project", "genre"),
            ("project", "category"),
            ("novel", "genre"),
        ):
            cursor: Any = bootstrap
            for key in path:
                cursor = cursor.get(key) if isinstance(cursor, dict) else None
            if isinstance(cursor, str) and cursor.strip():
                return cursor.strip()
    return ""


def infer_retrieval_backend(novel_dir: Path) -> str:
    state = load_json(novel_dir / "novel_state.json", {})
    configured = state.get("retrieval_backend", "bm25") if isinstance(state, dict) else "bm25"
    return configured if configured in {"bm25", "lexical", "tfidf"} else "bm25"


def build_knowledge_pack(
    *,
    project_root: Path,
    novel_dir: Path,
    chapter: int,
    title: str,
    platform: str = "",
    genre: str = "",
) -> dict[str, Any]:
    routes = load_routes(project_root)
    workspace = workspace_root()
    novel_dir = Path(novel_dir).resolve()
    platform = platform or novel_dir.parent.name
    book_title = novel_dir.name
    previous_file = find_chapter_file(novel_dir, chapter - 1) if chapter > 1 else None
    genre = genre or infer_genre(novel_dir)
    scene_text = " ".join(
        part for part in (title, chapter_outline_text(novel_dir, chapter)) if part
    )
    context = {
        "平台": platform,
        "书名": book_title,
        "chapter": chapter,
        "chapter_3": f"{chapter:03d}",
        "previous_chapter_file": rel(previous_file, workspace) if previous_file else "",
        "genre": genre,
        "题材": genre,
        "title": title,
    }

    required = []
    for item in routes.get("required", []):
        path = _replace_vars(item.get("path", ""), context)
        required.append(
            {**item, "path": path, "exists": _path_exists(path, item.get("scope", ""))}
        )

    selected: list[dict[str, Any]] = []
    for route in routes.get("routes", []):
        key = route.get("key", "")
        select = False
        reason = ""
        if key == "chapter_one" and chapter == 1:
            select, reason = True, "第1章"
        elif key == "opening" and chapter <= 5:
            select, reason = True, "前5章"
        elif key == "genre" and genre:
            select, reason = True, f"题材={genre}"
        elif key == "dialogue" and any(token in scene_text for token in ("对话", "交锋", "谈判", "质问")):
            select, reason = True, "标题或细纲命中对话/交锋"
        elif key == "high_pressure" and any(token in scene_text for token in ("危机", "暴露", "反派", "杀", "逼", "崩")):
            select, reason = True, "标题或细纲命中高压场景"
        elif route.get("chapter_max"):
            try:
                if chapter <= int(route["chapter_max"]):
                    select, reason = True, f"chapter <= {route['chapter_max']}"
            except (TypeError, ValueError):
                pass
        elif route.get("chapter_mod"):
            try:
                every = int(route["chapter_mod"])
                if every > 0 and chapter % every == 0:
                    select, reason = True, f"每 {every} 章"
            except (TypeError, ValueError):
                pass
        elif route.get("title_keywords") and any(
            str(token) in scene_text for token in route["title_keywords"]
        ):
            select, reason = True, "标题或细纲命中引擎方法关键词"
        if not select:
            continue
        files = []
        for file_path in route.get("files", []):
            path = _replace_vars(file_path, context)
            files.append({"path": path, "exists": _path_exists(path)})
        selected.append({"key": key, "name": route.get("name", key), "reason": reason, "files": files})

    packs = load_packs(project_root)
    selected_pack = select_pack(novel_dir, packs)
    if selected_pack:
        selected_keys = {route["key"] for route in selected}
        by_key = {route["key"]: route for route in selected}
        for route in _pack_selected_routes(selected_pack, selected_keys):
            existing = by_key.get(route["key"])
            if existing is None:
                selected.append(route)
                by_key[route["key"]] = route
            else:
                known = {file["path"] for file in existing.get("files", [])}
                existing["files"].extend(
                    file for file in route["files"] if file["path"] not in known
                )

    pack = {
        "schema_version": "1.0",
        "generated_at": now_iso(),
        "chapter": chapter,
        "title": title,
        "scene_text": scene_text[:800],
        "novel_dir": rel(novel_dir, workspace),
        "context": context,
        "required": required,
        "pack": (
            {
                "pack_id": selected_pack.get("pack_id", ""),
                "version": selected_pack.get("version", ""),
                "capabilities": list(selected_pack.get("capabilities", []) or []),
            }
            if selected_pack
            else {}
        ),
        "available_packs": [str(item.get("pack_id", "")) for item in packs],
        "selected_routes": selected,
        "available_routes": [
            {"key": route.get("key", ""), "name": route.get("name", ""), "trigger": route.get("trigger", "")}
            for route in routes.get("routes", [])
        ],
    }
    missing_required = [
        item["path"] for item in required if item.get("path") and not item.get("exists")
    ]
    missing_selected = [
        file["path"]
        for route in selected
        for file in route.get("files", [])
        if file.get("path") and not file.get("exists")
    ]
    pack["missing_required"] = missing_required
    pack["missing_selected"] = missing_selected
    pack["status"] = "ok" if not (missing_required or missing_selected) else "warning"

    retrieval_backend = infer_retrieval_backend(novel_dir)
    boost_prefixes = tuple(
        dict.fromkeys(
            prefix
            for route in selected
            for prefix in ROUTE_BOOST_PREFIXES.get(route["key"], ())
        )
    )
    selected_paths = tuple(
        dict.fromkeys(
            file["path"]
            for route in selected
            for file in route.get("files", [])
            if file.get("exists") and file.get("path")
        )
    )
    retrieval_query = " ".join(
        item
        for item in [
            genre,
            *(route.get("name", "") for route in selected),
            *(Path(path).stem for path in selected_paths),
            scene_text[:200],
        ]
        if item
    )
    try:
        # Stage 1: selected route directories. Stage 2: fill from all craft dirs.
        primary_prefixes = boost_prefixes or RETRIEVAL_PREFIXES
        results = (
            search_knowledge(
                workspace,
                retrieval_query,
                limit=8,
                backend=retrieval_backend,
                include_prefixes=primary_prefixes,
                boost_prefixes=boost_prefixes,
                exclude_paths=selected_paths,
            )
            if retrieval_query
            else []
        )
        for item in results:
            item["stage"] = "route" if boost_prefixes else "fallback"
        if boost_prefixes and len(results) < 8:
            remaining = 8 - len(results)
            fallback = search_knowledge(
                workspace,
                retrieval_query,
                limit=remaining,
                backend=retrieval_backend,
                include_prefixes=RETRIEVAL_PREFIXES,
                boost_prefixes=boost_prefixes,
                exclude_paths=(
                    *selected_paths,
                    *(item["path"] for item in results),
                ),
            )
            for item in fallback:
                item["stage"] = "fallback"
            results.extend(fallback)
        pack["retrieval"] = {
            "mode": retrieval_backend,
            "query": retrieval_query,
            "primary_prefixes": list(primary_prefixes),
            "boost_prefixes": list(boost_prefixes),
            "excluded_selected_files": list(selected_paths),
            "results": [
                item
                for item in results
                if not any(marker in Path(item["path"]).name for marker in RETRIEVAL_EXCLUDE_MARKERS)
            ],
        }
    except (OSError, RuntimeError, sqlite3.Error):
        pack["retrieval"] = {"mode": retrieval_backend, "query": retrieval_query, "results": [], "status": "unavailable"}
    return pack


def save_knowledge_pack(pack: dict[str, Any], output: Path) -> None:
    save_json(output, pack)


def build_and_save_chapter_pack(
    *,
    project_root: Path,
    novel_dir: Path,
    chapter: int,
    title: str,
    strict: bool = False,
) -> dict[str, Any]:
    """Build, save, and classify one chapter knowledge pack.

    ``strict`` turns missing required or selected route files into ``fail``;
    otherwise they are reported as ``warning``.
    """
    pack = build_knowledge_pack(
        project_root=project_root,
        novel_dir=novel_dir,
        chapter=chapter,
        title=title,
    )
    pack_path = novel_dir / "摘要" / f"chapter_{chapter:03d}_knowledge_pack.json"
    save_knowledge_pack(pack, pack_path)

    missing_required = [path for path in pack.get("missing_required", []) if path]
    missing_selected = [path for path in pack.get("missing_selected", []) if path]
    missing = [*missing_required, *missing_selected]
    status = "fail" if strict and missing else "warning" if missing else "pass"
    return {
        "pack": pack,
        "pack_path": pack_path,
        "missing_required": missing_required,
        "missing_selected": missing_selected,
        "status": status,
    }
