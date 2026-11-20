"""Web dashboard configuration."""

from __future__ import annotations

import sys
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parents[2]
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from novel_creation_promax.core.roots import plugin_root, workspace_root  # noqa: E402

# Workspace root: where novel_output/ lives.
PROJECT_ROOT = workspace_root()
PLUGIN_ROOT = plugin_root()

# Output directory
OUTPUT_DIR = PROJECT_ROOT / "novel_output"

# Scripts (ship with the plugin, not the workspace)
SCRIPTS_DIR = PLUGIN_ROOT / "novel_creation_promax" / "scripts"
MEMORY_SCRIPTS_DIR = PLUGIN_ROOT / "skills" / "novel-memory" / "scripts"
MEMORY_SCRIPT = MEMORY_SCRIPTS_DIR / "memory_manager.py"

# Supported platforms
PLATFORMS = ["番茄", "起点", "知乎", "七猫", "飞卢", "晋江"]

# Pipeline stages in order
STAGES = ["创意", "设定", "大纲", "细纲", "正文", "记忆更新", "完结复盘"]

# CORS
CORS_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8000"]
