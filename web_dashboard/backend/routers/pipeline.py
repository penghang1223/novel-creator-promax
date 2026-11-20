"""Pipeline execution API routes — run scripts as subprocesses."""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any, Optional
import sys

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from config import MEMORY_SCRIPT, PROJECT_ROOT, SCRIPTS_DIR

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from novel_creation_promax.core.paths import find_chapter_file, find_memory_dir
from utils.paths import get_novel_dir

router = APIRouter(prefix="/api/novels/{platform}/{name:path}/pipeline", tags=["pipeline"])

# In-memory job registry
jobs: dict[str, dict[str, Any]] = {}
job_logs: dict[str, list[dict[str, str]]] = {}


class PipelineRequest(BaseModel):
    chapter: Optional[int] = None
    extra_args: list[str] = Field(default_factory=list)


def _get_novel_dir(platform: str, name: str) -> Path:
    return get_novel_dir(platform, name)


def _get_chapter_file_from_dir(novel_dir: Path, ch_num: int) -> Optional[str]:
    if not ch_num:
        return None
    path = find_chapter_file(novel_dir, ch_num)
    return str(path) if path else None


def _add_log(job_id: str, level: str, message: str):
    import datetime
    entry = {
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "level": level,
        "message": message,
    }
    job_logs.setdefault(job_id, []).append(entry)


async def _run_script(job_id: str, cmd: list[str]):
    """Run a script as subprocess, capture output."""
    jobs[job_id]["status"] = "running"
    _add_log(job_id, "info", f"$ {' '.join(cmd)}")

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(PROJECT_ROOT),
        )

        async def read_stream(stream, prefix=""):
            while True:
                line = await stream.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").rstrip()
                if text:
                    _add_log(job_id, "info" if not prefix else "error", f"{prefix}{text}")

        await asyncio.gather(
            read_stream(proc.stdout),
            read_stream(proc.stderr, "[stderr] "),
        )

        await proc.wait()
        jobs[job_id]["status"] = "completed" if proc.returncode == 0 else "failed"
        jobs[job_id]["exit_code"] = proc.returncode
        _add_log(job_id, "info", f"Process exited with code {proc.returncode}")

    except Exception as e:
        jobs[job_id]["status"] = "error"
        _add_log(job_id, "error", str(e))


def _build_command(action: str, novel_dir: Path, chapter: Optional[int], extra_args: list) -> Optional[list]:
    """Build the CLI command for a pipeline action."""
    if extra_args:
        raise ValueError("不允许通过 Dashboard 注入额外命令行参数")

    import sys
    python = sys.executable
    scripts = SCRIPTS_DIR

    ch_file = None
    if chapter:
        ch_file = _get_chapter_file_from_dir(novel_dir, chapter)

    style_dna_path = find_memory_dir(novel_dir) / "style_dna_baseline.json"
    if not style_dna_path.is_file():
        style_dna_path = find_memory_dir(novel_dir) / "style_dna.json"
    style_command = [python, str(scripts / "style_calibrator.py")]
    character_command = [python, str(scripts / "character_consistency_checker.py")]
    if ch_file:
        style_command.extend([
            f"--input={ch_file}",
            f"--style-dna={style_dna_path}",
        ])
        character_command.extend([
            f"--input={ch_file}",
            f"--character-profile={find_memory_dir(novel_dir) / 'characters.json'}",
        ])
        if chapter:
            style_command.append(f"--output={novel_dir / '素材' / f'style_ch{chapter:03d}.json'}")
            character_command.append(f"--output={novel_dir / '素材' / f'character_ch{chapter:03d}.json'}")

    actions = {
        "write-pre": [python, str(scripts / "write_pipeline.py"), "pre", "--novel-dir", str(novel_dir)]
        + ([f"--chapter={chapter}", f"--title=第{chapter}章"] if chapter else []),

        "write-post": [python, str(scripts / "write_pipeline.py"), "post", "--novel-dir", str(novel_dir)]
        + ([f"--chapter={chapter}", f"--title=第{chapter}章"] if chapter else []),

        "pre-write-check": [python, str(scripts / "pre_write_check.py"), "--novel-dir", str(novel_dir)]
        + ([f"--chapter={chapter}"] if chapter else []),

        "gate-check": [python, str(scripts / "writing_gate.py")]
        + ([f"--chapter={ch_file}"] if ch_file else [])
        + ["--novel-dir", str(novel_dir)],

        "post-audit": [python, str(scripts / "post_write_audit.py")]
        + ([f"--chapter-file={ch_file}"] if ch_file else [])
        + ([f"--prev-file={_get_chapter_file_from_dir(novel_dir, chapter - 1)}"] if chapter and chapter > 1 else [])
        + ([f"--title=第{chapter}章"] if chapter else [])
        + ([f"--output={novel_dir / '素材' / f'audit_ch{chapter:03d}.json'}"] if chapter else [])
        + ([f"--novel-state={novel_dir / 'novel_state.json'}"] if chapter else []),

        "style-check": style_command,

        "character-check": character_command,

        "plot-check": [python, str(scripts / "plot_continuity_checker.py"), "--check", str(chapter or 1),
                        "--load", str(find_memory_dir(novel_dir) / "plot_logic.json")],

        "memory-sync": [python, str(MEMORY_SCRIPT), "sync-chapter"]
        + ([f"--input={novel_dir}/摘要/chapter_{chapter:03d}_summary.json"] if chapter else [])
        + [f"--memory-dir={find_memory_dir(novel_dir)}"],

        "memory-pack": [python, str(MEMORY_SCRIPT), "chapter-pack"]
        + ([f"--chapter={chapter}"] if chapter else [])
        + [f"--memory-dir={find_memory_dir(novel_dir)}"],

        "memory-stats": [python, str(MEMORY_SCRIPT), "stats", f"--memory-dir={find_memory_dir(novel_dir)}"],

        "generate-cover": [python, str(scripts / "generate_cover.py"), "--auto", f"--output={novel_dir}/cover.jpg"],
    }

    cmd = actions.get(action)
    if cmd is None:
        return None

    return cmd


@router.post("/{action}")
async def run_pipeline_action(platform: str, name: str, action: str, body: Optional[PipelineRequest] = None):
    """Execute a pipeline action."""
    body = body or PipelineRequest()
    try:
        novel_dir = _get_novel_dir(platform, name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not novel_dir.is_dir():
        raise HTTPException(status_code=404, detail="Novel directory not found")
    job_id = str(uuid.uuid4())[:8]

    try:
        cmd = _build_command(action, novel_dir, body.chapter, body.extra_args)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if cmd is None:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")

    jobs[job_id] = {"id": job_id, "action": action, "status": "pending", "exit_code": None}
    job_logs[job_id] = []

    asyncio.create_task(_run_script(job_id, cmd))

    return {"job_id": job_id, "action": action}


@router.get("/jobs/{job_id}")
def get_job_status(job_id: str):
    """Get job status and logs."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        **jobs[job_id],
        "logs": job_logs.get(job_id, []),
    }


@router.get("/jobs")
def list_jobs():
    """List recent jobs."""
    return list(jobs.values())[-20:]
