---
description: 调研平台热门写作方向、榜单题材与差异化机会
argument-hint: "[平台] [题材/受众] [时间窗口]"
---

读取并执行 `${CLAUDE_PLUGIN_ROOT}/skills/novel-market-research/SKILL.md`。

## 写入前先确认工作区

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/workspace.py" --workspace "${CLAUDE_PROJECT_DIR}" status --json
```

`dangerous=plugin_root|root` 时停止；`confirmed=false` 且 `legacy_books=0` 时，展示绝对路径与 `write_paths`，等用户确认后再运行 `workspace.py confirm`。

要求：

- 平台未指定时先问一次，不要默认番茄。
- 结论区分 `[事实]`、`[推断]`、`[建议]`、`[待验证]`，外部结论带 URL 与访问日期。
- 报告写入 `${CLAUDE_PROJECT_DIR}/素材/调研/`。
- 结尾给 3–5 个可执行选题和下一步 `/novel-creator-pro:idea` 命令。

## 阶段记录

报告生成后，如果工作流已启动，记录证据：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/workflow.py" --workspace "${CLAUDE_PROJECT_DIR}" \
  advance --to research
```

工作流未启动时先：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/workflow.py" --workspace "${CLAUDE_PROJECT_DIR}" \
  start --platform "{平台}" --genre "{题材}"
```
