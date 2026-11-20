---
description: 生成可立项的创意卡并做五维评分
argument-hint: "[平台] [题材] [数量]"
---

读取并执行 `${CLAUDE_PLUGIN_ROOT}/skills/novel-idea/SKILL.md`。

要求：

- 默认生成 5 个，最多 10 个。
- 创意必须覆盖至少 3 种核心情绪/爽点，不能只换皮。
- 每个创意用 `${CLAUDE_PLUGIN_ROOT}/tools/idea_score.py` 评分。
- 创意卡写入 `${CLAUDE_PROJECT_DIR}/创意/创意卡_{日期}.md`。
- 用户选定后交给立项技能，不直接写正文。

## 阶段记录

创意卡生成后：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/workflow.py" --workspace "${CLAUDE_PROJECT_DIR}" \
  advance --to idea
```

如果没有调研报告，该门禁会失败；先完成 `/research`，或由用户明确 `--force --reason`。
