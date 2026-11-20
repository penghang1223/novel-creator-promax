#!/usr/bin/env python3
"""Validate chapter JSON contracts and optionally fail on errors."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from novel_creation_promax.core.contracts import save_contract_report, validate_chapter_contracts  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="校验章节 JSON 契约")
    parser.add_argument("--novel-dir", required=True)
    parser.add_argument("--chapter", required=True, type=int)
    parser.add_argument("--no-save", action="store_true")
    args = parser.parse_args()
    novel_dir = Path(args.novel_dir).resolve()
    report = validate_chapter_contracts(novel_dir, args.chapter)
    if not args.no_save:
        report["report_path"] = str(save_contract_report(novel_dir, args.chapter, report))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
