---
description: 查看或推进项目级工作流阶段
argument-hint: "[status|advance] [目标阶段]"
---

读取并执行 `${CLAUDE_PLUGIN_ROOT}/skills/novel-workflow/SKILL.md`。

默认先运行：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/workflow.py" --workspace "${CLAUDE_PROJECT_DIR}" status
```

`status` 只读，不需要确认。执行 `start` 前先确认工作区：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/workspace.py" --workspace "${CLAUDE_PROJECT_DIR}" status --json
```

- `dangerous=plugin_root|root`：停止，不得启动。
- `confirmed=false` 且 `legacy_books=0`：展示绝对路径等用户确认，再运行 `workspace.py confirm`；不要自行加 `--confirm-workspace`。
- `confirmed=false` 且 `legacy_books>0`：可直接用 `--confirm-workspace` 启动，或先 `workspace.py confirm --legacy`。

只报告状态时不要推进。推进前必须满足门禁；跳阶段必须 `--force --reason` 并记录。
