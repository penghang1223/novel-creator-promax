#!/usr/bin/env python3
"""番茄登录入口（桥接外部 Playwright 引擎）。

运行后按提示扫码登录，登录态保存到工作区：
``{workspace}/.novel_publish/fanqie/state.json``
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bridge  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(_bridge.run("login.py", sys.argv[1:]))
