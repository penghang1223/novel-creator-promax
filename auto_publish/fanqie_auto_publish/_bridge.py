"""Bridge helpers for the Fanqie publisher.

The Playwright publishing engine is not vendored into this repository. It is
resolved from (in order):

1. ``NOVEL_FANQIE_PUBLISHER`` pointing at the engine file or its directory
2. ``~/fanqie_auto_publish/``
3. ``{workspace}/.novel_publish/fanqie/engine/``
4. ``auto_publish/fanqie_auto_publish/engine/``

The engine always runs with its working directory set to
``{workspace}/.novel_publish/fanqie`` so chapter drafts, login state and
uploaded archives stay in the user's workspace, never in the plugin.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ENGINE_SCRIPTS = ("publish.py", "login.py")


def workspace() -> Path:
    raw = (
        os.environ.get("NOVEL_WORKSPACE_ROOT")
        or os.environ.get("CLAUDE_PROJECT_DIR")
        or os.getcwd()
    )
    return Path(raw).expanduser().resolve()


def publish_dir() -> Path:
    return workspace() / ".novel_publish" / "fanqie"


def _candidate(script_name: str) -> list[Path]:
    candidates: list[Path] = []
    configured = os.environ.get("NOVEL_FANQIE_PUBLISHER", "").strip()
    if configured:
        path = Path(configured).expanduser()
        candidates.append(path.parent / script_name if path.is_file() else path / script_name)
    candidates.append(Path.home() / "fanqie_auto_publish" / script_name)
    candidates.append(publish_dir() / "engine" / script_name)
    candidates.append(Path(__file__).resolve().parent / "engine" / script_name)
    return candidates


def resolve_engine(script_name: str = "publish.py") -> Path:
    for candidate in _candidate(script_name):
        if candidate.is_file():
            return candidate.resolve()
    searched = "\n".join(f"  - {item}" for item in _candidate(script_name))
    raise FileNotFoundError(
        "未找到番茄发布引擎。请安装 fanqie_auto_publish，或设置 NOVEL_FANQIE_PUBLISHER。\n"
        f"已查找：\n{searched}\n"
        "示例：export NOVEL_FANQIE_PUBLISHER=$HOME/fanqie_auto_publish"
    )


def ensure_layout() -> Path:
    base = publish_dir()
    for child in ("chapters", "short_chapters", "uploaded", "short_uploaded"):
        (base / child).mkdir(parents=True, exist_ok=True)
    return base


def sync_state(engine: Path, base: Path) -> None:
    """Reuse an existing login state from the engine directory on first run."""
    target = base / "state.json"
    if target.exists():
        return
    source = engine.parent / "state.json"
    if source.is_file():
        shutil.copy2(source, target)


def check_playwright() -> str:
    if os.environ.get("NOVEL_SKIP_PLAYWRIGHT_CHECK") == "1":
        return ""
    try:
        import playwright  # noqa: F401
    except ImportError:
        return (
            "缺少 playwright。请安装：\n"
            "  python3 -m pip install playwright\n"
            "  python3 -m playwright install chromium"
        )
    return ""


def run(script_name: str, argv: list[str]) -> int:
    try:
        engine = resolve_engine(script_name)
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    missing = check_playwright()
    if missing:
        print(f"[ERROR] {missing}", file=sys.stderr)
        return 2

    base = ensure_layout()
    sync_state(engine, base)
    print(f"[INFO] 引擎: {engine}")
    print(f"[INFO] 工作目录: {base}")
    completed = subprocess.run([sys.executable, str(engine), *argv], cwd=str(base))
    return completed.returncode
