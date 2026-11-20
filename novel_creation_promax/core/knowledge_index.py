"""Searchable knowledge-base read model.

The knowledge base files remain the source of truth. This module builds a
rebuildable SQLite lexical index so routing and retrieval do not repeatedly
scan the whole tree. It deliberately has no embedding dependency; the result
shape can later be backed by an embedding provider without changing callers.
"""

from __future__ import annotations

import math
import os
import re
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from .jsonio import now_iso
from .roots import asset_path, plugin_root

KNOWLEDGE_INDEX_RELATIVE_PATH = Path("novel_output") / "_workspace" / "index" / "knowledge_index.sqlite3"
INDEX_SCHEMA_VERSION = "1.0"
SUPPORTED_SUFFIXES = {".md", ".txt", ".json", ".yaml", ".yml"}
_LATIN_TOKEN = re.compile(r"[a-z0-9][a-z0-9_\-]{1,}", re.IGNORECASE)
_CJK_RUN = re.compile(r"[\u4e00-\u9fff]+")


def index_path(project_root: Path) -> Path:
    return project_root / KNOWLEDGE_INDEX_RELATIVE_PATH


def _iter_documents(knowledge_root: Path) -> Iterable[Path]:
    if not knowledge_root.is_dir():
        return
    for path in sorted(knowledge_root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        if any(part.startswith(".") for part in path.relative_to(knowledge_root).parts):
            continue
        yield path


def _terms(text: str) -> list[str]:
    result = [item.lower() for item in _LATIN_TOKEN.findall(text.lower())]
    for run in _CJK_RUN.findall(text):
        result.extend(run[index:index + 2] for index in range(len(run) - 1))
    return [item for item in result if item]


def _title(text: str, path: Path) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or path.stem
    return path.stem


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode = WAL")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY,
            path TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            mtime_ns INTEGER NOT NULL,
            size INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS terms (
            document_id INTEGER NOT NULL,
            term TEXT NOT NULL,
            frequency INTEGER NOT NULL,
            PRIMARY KEY (document_id, term),
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_terms_term ON terms(term);
        """
    )
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def sync_knowledge_index(project_root: Path, *, knowledge_root: Path | None = None) -> dict[str, Any]:
    """Rebuild the lexical read model from one or more knowledge roots.

    In plugin mode the workspace may contain only project-level knowledge
    (``knowledge_base/80_Projects``), so the plugin knowledge base is merged
    in as well. Workspace files override plugin files with the same relative
    path. Tests and callers passing ``knowledge_root`` keep single-root
    behavior.
    """
    project_root = project_root.resolve()
    roots: list[Path] = []
    if knowledge_root is not None:
        roots = [knowledge_root.resolve()]
    else:
        plugin_env = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.environ.get("NOVEL_PLUGIN_ROOT")
        workspace_kb = project_root / "knowledge_base"
        if plugin_env:
            plugin_kb = plugin_root() / "knowledge_base"
            for candidate in (plugin_kb, workspace_kb):
                if candidate.is_dir() and candidate.resolve() not in roots:
                    roots.append(candidate.resolve())
        else:
            roots = [workspace_kb.resolve() if workspace_kb.is_dir() else asset_path("knowledge_base").resolve()]

    documents: dict[str, Path] = {}
    for root in roots:
        for document in _iter_documents(root):
            try:
                relative = document.relative_to(root).as_posix()
            except ValueError:
                continue
            documents[relative] = document

    path = index_path(project_root)
    connection = _connect(path)
    try:
        connection.execute("DELETE FROM terms")
        connection.execute("DELETE FROM documents")
        document_count = 0
        term_count = 0
        for relative, document in sorted(documents.items()):
            try:
                body = document.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            stored_path = (Path("knowledge_base") / relative).as_posix()
            result = connection.execute(
                "INSERT INTO documents(path, title, body, mtime_ns, size) VALUES (?, ?, ?, ?, ?)",
                (stored_path, _title(body, document), body, document.stat().st_mtime_ns, document.stat().st_size),
            )
            document_id = int(result.lastrowid)
            frequencies: dict[str, int] = {}
            for term in _terms(body):
                frequencies[term] = frequencies.get(term, 0) + 1
            connection.executemany(
                "INSERT INTO terms(document_id, term, frequency) VALUES (?, ?, ?)",
                [(document_id, term, frequency) for term, frequency in frequencies.items()],
            )
            document_count += 1
            term_count += len(frequencies)
        connection.execute("DELETE FROM metadata")
        connection.executemany(
            "INSERT INTO metadata(key, value) VALUES (?, ?)",
            [
                ("schema_version", INDEX_SCHEMA_VERSION),
                ("knowledge_root", ";".join(str(root) for root in roots)),
                ("indexed_at", now_iso()),
            ],
        )
        connection.commit()
    finally:
        connection.close()
    return {
        "schema_version": INDEX_SCHEMA_VERSION,
        "path": str(path),
        "knowledge_root": ";".join(str(root) for root in roots),
        "documents": document_count,
        "terms": term_count,
    }


def _prefix_filter(prefixes: tuple[str, ...]) -> tuple[str, list[str]]:
    """SQL fragment limiting results to technique directories (optional)."""
    if not prefixes:
        return "", []
    clauses = " OR ".join("d.path LIKE ?" for _ in prefixes)
    params = [f"{prefix.rstrip('/')}/%" for prefix in prefixes]
    return f" AND ({clauses})", params


def _search_tfidf(
    connection: sqlite3.Connection,
    query_terms: list[str],
    limit: int,
    include_prefixes: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    document_count = int(connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0] or 0)
    if not document_count:
        return []
    placeholders = ",".join("?" for _ in query_terms)
    filter_sql, filter_params = _prefix_filter(include_prefixes)
    rows = connection.execute(
        f"""
        SELECT d.id, d.path, d.title, d.body, t.term, t.frequency,
               (SELECT COUNT(*) FROM terms df WHERE df.term = t.term) AS document_frequency
        FROM terms t
        JOIN documents d ON d.id = t.document_id
        WHERE t.term IN ({placeholders}){filter_sql}
        """,
        [*query_terms, *filter_params],
    ).fetchall()
    query_frequency = {term: query_terms.count(term) for term in query_terms}
    query_weights = {
        term: (1.0 + math.log(frequency)) * (math.log((document_count + 1) / (df + 1)) + 1.0)
        for term, frequency in query_frequency.items()
        for df in [sum(1 for row in rows if row["term"] == term)]
    }
    query_norm = math.sqrt(sum(value * value for value in query_weights.values())) or 1.0
    documents: dict[int, dict[str, Any]] = {}
    for row in rows:
        item = documents.setdefault(
            int(row["id"]),
            {"path": row["path"], "title": row["title"], "body": row["body"], "weights": {}},
        )
        term = row["term"]
        idf = math.log((document_count + 1) / (int(row["document_frequency"]) + 1)) + 1.0
        item["weights"][term] = (1.0 + math.log(int(row["frequency"]))) * idf
    ranked = []
    for item in documents.values():
        numerator = sum(item["weights"].get(term, 0.0) * weight for term, weight in query_weights.items())
        document_norm = math.sqrt(sum(value * value for value in item["weights"].values())) or 1.0
        matched = len(item["weights"])
        ranked.append((numerator / (query_norm * document_norm), matched, item))
    ranked.sort(key=lambda value: (-value[0], -value[1], value[2]["path"]))
    return [
        {
            "path": item["path"],
            "title": item["title"],
            "score": round(score, 6),
            "matched_terms": matched,
            "snippet": " ".join(line.strip() for line in item["body"].splitlines() if line.strip())[:240],
        }
        for score, matched, item in ranked[: max(1, min(limit, 50))]
    ]


def _snippet(body: str) -> str:
    return " ".join(line.strip() for line in body.splitlines() if line.strip())[:240]


def _search_lexical(
    connection: sqlite3.Connection,
    query_terms: list[str],
    limit: int,
    include_prefixes: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    placeholders = ",".join("?" for _ in query_terms)
    filter_sql, filter_params = _prefix_filter(include_prefixes)
    rows = connection.execute(
        f"""
        SELECT d.path, d.title, d.body,
               SUM(t.frequency) AS score,
               COUNT(DISTINCT t.term) AS matched_terms
        FROM terms t
        JOIN documents d ON d.id = t.document_id
        WHERE t.term IN ({placeholders}){filter_sql}
        GROUP BY d.id
        ORDER BY matched_terms DESC, score DESC, d.path ASC
        LIMIT ?
        """,
        [*query_terms, *filter_params, max(1, min(limit, 50))],
    ).fetchall()
    return [
        {
            "path": row["path"],
            "title": row["title"],
            "score": int(row["score"] or 0),
            "matched_terms": int(row["matched_terms"] or 0),
            "snippet": _snippet(str(row["body"])),
        }
        for row in rows
    ]


def _search_bm25(
    connection: sqlite3.Connection,
    query_terms: list[str],
    limit: int,
    include_prefixes: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    """BM25 with document-length normalization; better than raw TF for long docs."""
    document_count = int(connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0] or 0)
    if not document_count:
        return []
    average_length = float(
        connection.execute("SELECT AVG(LENGTH(body)) FROM documents").fetchone()[0] or 1.0
    )
    placeholders = ",".join("?" for _ in query_terms)
    document_frequency = {
        str(row["term"]): int(row["document_frequency"])
        for row in connection.execute(
            f"""
            SELECT term, COUNT(*) AS document_frequency
            FROM terms
            WHERE term IN ({placeholders})
            GROUP BY term
            """,
            query_terms,
        ).fetchall()
    }
    filter_sql, filter_params = _prefix_filter(include_prefixes)
    rows = connection.execute(
        f"""
        SELECT d.id, d.path, d.title, d.body, t.term, t.frequency,
               LENGTH(d.body) AS doc_length
        FROM terms t
        JOIN documents d ON d.id = t.document_id
        WHERE t.term IN ({placeholders}){filter_sql}
        """,
        [*query_terms, *filter_params],
    ).fetchall()

    k1, b = 1.5, 0.75
    scores: dict[int, float] = {}
    matched: dict[int, set[str]] = {}
    documents: dict[int, sqlite3.Row] = {}
    for row in rows:
        doc_id = int(row["id"])
        documents.setdefault(doc_id, row)
        term = str(row["term"])
        frequency = int(row["frequency"] or 0)
        df = document_frequency.get(term, 1)
        idf = math.log(1 + (document_count - df + 0.5) / (df + 0.5))
        doc_length = float(row["doc_length"] or 1)
        denominator = frequency + k1 * (1 - b + b * doc_length / average_length)
        if denominator <= 0:
            continue
        scores[doc_id] = scores.get(doc_id, 0.0) + idf * (frequency * (k1 + 1)) / denominator
        matched.setdefault(doc_id, set()).add(term)

    ranked = sorted(
        scores.items(),
        key=lambda item: (-item[1], -len(matched[item[0]]), documents[item[0]]["path"]),
    )
    return [
        {
            "path": documents[doc_id]["path"],
            "title": documents[doc_id]["title"],
            "score": round(score, 6),
            "matched_terms": len(matched[doc_id]),
            "snippet": _snippet(str(documents[doc_id]["body"])),
        }
        for doc_id, score in ranked[: max(1, min(limit, 50))]
    ]


def _apply_boosts(
    results: list[dict[str, Any]],
    query_terms: list[str],
    boost_prefixes: tuple[str, ...],
) -> list[dict[str, Any]]:
    if not boost_prefixes:
        return results
    boosted: list[dict[str, Any]] = []
    for item in results:
        factor = 1.0
        path = str(item["path"])
        if any(path.startswith(prefix.rstrip("/") + "/") for prefix in boost_prefixes):
            factor *= 1.35
        title = str(item.get("title", "")).lower()
        if any(term in title for term in query_terms if len(term) >= 2):
            factor *= 1.15
        boosted.append(
            {
                **item,
                "score": round(float(item["score"]) * factor, 6),
                "boost": round(factor, 3),
            }
        )
    boosted.sort(key=lambda item: (-item["score"], -item.get("matched_terms", 0), item["path"]))
    return boosted


def search_knowledge(
    project_root: Path,
    query: str,
    *,
    limit: int = 8,
    backend: str = "bm25",
    include_prefixes: tuple[str, ...] = (),
    boost_prefixes: tuple[str, ...] = (),
    exclude_paths: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    """Return ranked paths and snippets for a knowledge query.

    ``include_prefixes`` restricts results to given ``knowledge_base/``
    subdirectories; ``boost_prefixes`` reranks selected route directories.
    ``exclude_paths`` drops files already listed as selected route inputs, so
    retrieval stays supplementary instead of repeating the core reading list.
    """
    query_terms = list(dict.fromkeys(_terms(query)))
    if not query_terms:
        return []
    path = index_path(project_root)
    if not path.is_file():
        sync_knowledge_index(project_root)
    connection = _connect(path)
    try:
        widen = 4 if (boost_prefixes or exclude_paths) else 1
        fetch_limit = max(1, min(max(limit * widen, limit), 50))
        if backend == "bm25":
            raw = _search_bm25(connection, query_terms, fetch_limit, include_prefixes)
        elif backend in {"tfidf", "vector"}:
            raw = _search_tfidf(connection, query_terms, fetch_limit, include_prefixes)
        else:
            raw = _search_lexical(connection, query_terms, fetch_limit, include_prefixes)
    finally:
        connection.close()
    results = _apply_boosts(raw, query_terms, boost_prefixes)
    if exclude_paths:
        excluded = set(exclude_paths)
        results = [item for item in results if item["path"] not in excluded]
    return results[: max(1, min(limit, 50))]
