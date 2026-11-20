---
description: 生成或更新总大纲、分卷和章节细纲
argument-hint: "[书名] [卷/章节范围]"
---

读取并执行 `${CLAUDE_PLUGIN_ROOT}/skills/novel-project-planning/SKILL.md` 的大纲阶段。

要求：

- 先读工作区 `设定/` 和 `结构/`，再写大纲与细纲。
- 细纲必须包含章节节点、伏笔、爽点和截断点。
- 改动写入 `${CLAUDE_PROJECT_DIR}/novel_output/{平台}/{书名}/`。
