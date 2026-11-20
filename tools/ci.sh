#!/usr/bin/env bash
# Local CI entry: run before push or in any CI runner.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python3 -m unittest discover -s tests
python3 novel_creation_promax/scripts/skill_health_check.py
python3 tools/plugin_doctor.py --root .
