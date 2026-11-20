#!/usr/bin/env python3
"""Validate one chapter's optional tension-curve contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from novel_creation_promax.core.tension_curve import validate_chapter_tension  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="校验章节张力曲线")
    parser.add_argument("--novel-dir", required=True)
    parser.add_argument("--chapter", required=True, type=int)
    parser.add_argument("--no-save", action="store_true")
    args = parser.parse_args()
    report = validate_chapter_tension(Path(args.novel_dir).resolve(), args.chapter, save=not args.no_save)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] in {"pass", "skipped"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
