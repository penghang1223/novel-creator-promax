---
description: 新书立项：平台、题材、设定、大纲、细纲与 seal 门禁
argument-hint: "[平台] [题材/创意]"
---

读取并执行 `${CLAUDE_PLUGIN_ROOT}/skills/novel-project-planning/SKILL.md`。

## 写入前先确认工作区

1. 运行：

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/tools/workspace.py" --workspace "${CLAUDE_PROJECT_DIR}" status --json
   ```

2. `dangerous` 为 `plugin_root` 或 `root`：停止，不得确认。
3. `confirmed=true`：继续。
4. `confirmed=false` 且 `legacy_books>0`：运行 `workspace.py confirm --legacy` 后继续。
5. `confirmed=false` 且 `legacy_books=0`：向用户展示 `workspace` 绝对路径和 `write_paths`，等待用户明确确认后再运行 `workspace.py confirm`。用户要求换目录时停止，提示其在目标目录重新打开 Claude Code。

确认后传 `--confirm-workspace` 给 `init`，或先运行 `workspace.py confirm`。

## 要求

- 新项目目录位于 `${CLAUDE_PROJECT_DIR}/novel_output/{平台}/{书名}`。
- 完成 `project_bootstrap_pipeline.py init` 后，按清单补齐资料，再运行 `seal`。
- `seal` 未通过时，不要进入第 1 章正文。

## 阶段记录

`seal` 通过后：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/workflow.py" --workspace "${CLAUDE_PROJECT_DIR}" \
  advance --to init --novel-dir "${CLAUDE_PROJECT_DIR}/novel_output/{平台}/{书名}"
```
