#!/usr/bin/env bash
# Local CI entry: run before push or in any CI runner.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python3 -m unittest discover -s tests
python3 tools/run_skill_evals.py
python3 novel_creation_promax/scripts/skill_health_check.py
python3 tools/pack_check.py
python3 tools/plugin_doctor.py --plugin-only
if [ -n "${NOVEL_WORKSPACE_ROOT:-}" ]; then
  python3 tools/plugin_doctor.py --root "$NOVEL_WORKSPACE_ROOT"
  python3 tools/dashboard.py --workspace "$NOVEL_WORKSPACE_ROOT" --check
fi
