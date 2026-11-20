"""Aggregated index and quality-debt endpoints for the dashboard."""

from __future__ import annotations

import sys

from fastapi import APIRouter, Query

from config import PROJECT_ROOT

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from novel_creation_promax.core.jsonio import load_json  # noqa: E402
from novel_creation_promax.core.knowledge_index import index_path as knowledge_index_path  # noqa: E402
from novel_creation_promax.core.knowledge_index import search_knowledge, sync_knowledge_index  # noqa: E402
from novel_creation_promax.core.paths import list_chapter_files  # noqa: E402
from novel_creation_promax.core.story_index import (  # noqa: E402
    index_path,
    iter_output_projects,
    query_projects,
    sync_root_index,
)
from novel_creation_promax.core.tension_curve import tension_report_path  # noqa: E402
from tools.quality_debt import build_report  # noqa: E402


router = APIRouter(prefix="/api/insights", tags=["insights"])


@router.get("/index")
def get_story_index():
    sync = sync_root_index(PROJECT_ROOT)
    return {"sync": sync, "projects": query_projects(index_path(PROJECT_ROOT))}


@router.get("/quality-debt")
def get_quality_debt():
    report = build_report(PROJECT_ROOT)
    report["index"] = sync_root_index(PROJECT_ROOT)
    return report


@router.get("/tension")
def get_tension_insights():
    projects = []
    all_values: list[float] = []
    failed = 0
    for novel_dir in iter_output_projects(PROJECT_ROOT / "novel_output"):
        chapters = []
        for chapter, _chapter_file in list_chapter_files(novel_dir):
            summary = load_json(novel_dir / "摘要" / f"chapter_{chapter:03d}_summary.json", {})
            metrics = summary.get("chapter_metrics", {}) if isinstance(summary, dict) else {}
            curve = metrics.get("tension_curve", []) if isinstance(metrics, dict) else []
            values = []
            if isinstance(curve, list):
                for point in curve:
                    value = point.get("value", point.get("tension")) if isinstance(point, dict) else point
                    if isinstance(value, (int, float)):
                        values.append(float(value))
            report = load_json(tension_report_path(novel_dir, chapter), {})
            report_points = report.get("points", []) if isinstance(report, dict) else []
            if not values and isinstance(report_points, list):
                values = [
                    float(point.get("value"))
                    for point in report_points
                    if isinstance(point, dict) and isinstance(point.get("value"), (int, float))
                ]
            if not values and isinstance(metrics, dict):
                legacy_value = metrics.get("narrative_tension", summary.get("narrative_tension"))
                if isinstance(legacy_value, (int, float)):
                    values = [float(legacy_value)]
            status = report.get("status", "skipped") if isinstance(report, dict) else "skipped"
            estimated = bool(report.get("estimated", False)) if isinstance(report, dict) else False
            if status == "fail":
                failed += 1
            all_values.extend(values)
            if values or status != "skipped":
                chapters.append(
                    {
                        "chapter": chapter,
                        "values": values,
                        "average": round(sum(values) / len(values), 2) if values else None,
                        "peak": max(values) if values else None,
                        "status": status,
                        "estimated": estimated,
                    }
                )
        if chapters:
            projects.append({"novel_dir": str(novel_dir.relative_to(PROJECT_ROOT)), "chapters": chapters})
    return {
        "summary": {
            "projects": len(projects),
            "chapters": sum(len(project["chapters"]) for project in projects),
            "points": len(all_values),
            "average": round(sum(all_values) / len(all_values), 2) if all_values else None,
            "peak": max(all_values) if all_values else None,
            "failed": failed,
        },
        "projects": projects,
    }


@router.get("/knowledge-search")
def search_knowledge_insights(
    q: str = Query(default="", min_length=0, max_length=200),
    limit: int = Query(default=8, ge=1, le=50),
    backend: str = Query(default="lexical", pattern="^(lexical|tfidf)$"),
):
    if not q.strip():
        return {"query": q, "backend": backend, "results": []}
    if not knowledge_index_path(PROJECT_ROOT).is_file():
        sync_knowledge_index(PROJECT_ROOT)
    return {"query": q, "backend": backend, "results": search_knowledge(PROJECT_ROOT, q, limit=limit, backend=backend)}
