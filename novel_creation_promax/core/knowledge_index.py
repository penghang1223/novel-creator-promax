"""Searchable knowledge-base read model.

The knowledge base files remain the source of truth. This module builds a
rebuildable SQLite lexical index so routing and retrieval do not repeatedly
scan the whole tree. It deliberately has no embedding dependency; the result
shape can later be backed by an embedding provider without changing callers.
"""

from __future__ import annotations

import re
import sqlite3
import math
from pathlib import Path
from typing import Any, Iterable

from .jsonio import now_iso
from .roots import asset_path

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
    """Rebuild the small lexical read model from knowledge-base source files."""
    project_root = project_root.resolve()
    if knowledge_root is None:
        workspace_kb = project_root / "knowledge_base"
        knowledge_root = workspace_kb if workspace_kb.is_dir() else asset_path("knowledge_base")
    knowledge_root = knowledge_root.resolve()
    path = index_path(project_root)
    connection = _connect(path)
    try:
        connection.execute("DELETE FROM terms")
        connection.execute("DELETE FROM documents")
        document_count = 0
        term_count = 0
        for document in _iter_documents(knowledge_root):
            try:
                body = document.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            try:
                relative = (Path("knowledge_base") / document.relative_to(knowledge_root)).as_posix()
            except ValueError:
                relative = document.as_posix()
            result = connection.execute(
                "INSERT INTO documents(path, title, body, mtime_ns, size) VALUES (?, ?, ?, ?, ?)",
                (relative, _title(body, document), body, document.stat().st_mtime_ns, document.stat().st_size),
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
                ("knowledge_root", str(knowledge_root)),
                ("indexed_at", now_iso()),
            ],
        )
        connection.commit()
    finally:
        connection.close()
    return {
        "schema_version": INDEX_SCHEMA_VERSION,
        "path": str(path),
        "knowledge_root": str(knowledge_root),
        "documents": document_count,
        "terms": term_count,
    }


def _search_tfidf(connection: sqlite3.Connection, query_terms: list[str], limit: int) -> list[dict[str, Any]]:
    document_count = int(connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0] or 0)
    if not document_count:
        return []
    placeholders = ",".join("?" for _ in query_terms)
    rows = connection.execute(
        f"""
        SELECT d.id, d.path, d.title, d.body, t.term, t.frequency,
               (SELECT COUNT(*) FROM terms df WHERE df.term = t.term) AS document_frequency
        FROM terms t
        JOIN documents d ON d.id = t.document_id
        WHERE t.term IN ({placeholders})
        """,
        query_terms,
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


def search_knowledge(
    project_root: Path,
    query: str,
    *,
    limit: int = 8,
    backend: str = "lexical",
) -> list[dict[str, Any]]:
    """Return ranked paths and snippets for a lexical knowledge query."""
    query_terms = list(dict.fromkeys(_terms(query)))
    if not query_terms:
        return []
    path = index_path(project_root)
    if not path.is_file():
        sync_knowledge_index(project_root)
    connection = _connect(path)
    try:
        if backend in {"tfidf", "vector"}:
            return _search_tfidf(connection, query_terms, limit)
        placeholders = ",".join("?" for _ in query_terms)
        rows = connection.execute(
            f"""
            SELECT d.path, d.title, d.body,
                   SUM(t.frequency) AS score,
                   COUNT(DISTINCT t.term) AS matched_terms
            FROM terms t
            JOIN documents d ON d.id = t.document_id
            WHERE t.term IN ({placeholders})
            GROUP BY d.id
            ORDER BY matched_terms DESC, score DESC, d.path ASC
            LIMIT ?
            """,
            [*query_terms, max(1, min(limit, 50))],
        ).fetchall()
    finally:
        connection.close()

    results: list[dict[str, Any]] = []
    for row in rows:
        body = str(row["body"])
        snippet = " ".join(line.strip() for line in body.splitlines() if line.strip())[:240]
        results.append(
            {
                "path": row["path"],
                "title": row["title"],
                "score": int(row["score"] or 0),
                "matched_terms": int(row["matched_terms"] or 0),
                "snippet": snippet,
            }
        )
    return results
