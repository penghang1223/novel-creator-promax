---
description: 查看或推进项目级工作流阶段
argument-hint: "[status|advance] [目标阶段]"
---

读取并执行 `${CLAUDE_PLUGIN_ROOT}/skills/novel-workflow/SKILL.md`。

默认先运行：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/workflow.py" --workspace "${CLAUDE_PROJECT_DIR}" status
```

只报告状态时不要推进。推进前必须满足门禁；跳阶段必须 `--force --reason` 并记录。
