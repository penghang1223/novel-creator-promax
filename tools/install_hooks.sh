#!/bin/bash
# 安装版本化 git hooks（.githooks/ → core.hooksPath）
set -e

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

chmod +x .githooks/pre-commit 2>/dev/null || true
git config core.hooksPath .githooks

echo "[OK] git hooks 已启用: core.hooksPath=$(git config core.hooksPath)"
echo "     已安装: .githooks/pre-commit（章节写作门禁）"
echo "     临时跳过: git commit --no-verify"
