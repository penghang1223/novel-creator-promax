#!/usr/bin/env python3
"""番茄发布器入口（桥接外部 Playwright 引擎）。

用法与其他平台发布器一致：

    python3 publish.py --book "书名" --count 3 --draft
    python3 publish.py --short --book "短故事名"
    python3 publish.py --check          # 只检查引擎与依赖

章节、登录态和归档都在工作区 ``.novel_publish/fanqie/``，不写插件目录。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bridge  # noqa: E402


def main() -> int:
    argv = sys.argv[1:]
    if "--check" in argv:
        try:
            engine = _bridge.resolve_engine("publish.py")
        except FileNotFoundError as exc:
            print(f"[ERROR] {exc}", file=sys.stderr)
            return 2
        missing = _bridge.check_playwright()
        print(f"引擎: {engine}")
        print(f"发布目录: {_bridge.publish_dir()}")
        if missing:
            print(f"[ERROR] {missing}", file=sys.stderr)
            return 2
        print("检查通过")
        return 0
    return _bridge.run("publish.py", argv)


if __name__ == "__main__":
    raise SystemExit(main())
