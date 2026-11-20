---
description: 润色指定章节并记录修订历史
argument-hint: "[书名] 第N章 [方向]"
---

读取并执行 `${CLAUDE_PLUGIN_ROOT}/skills/novel-chapter-write/SKILL.md` 的润色路径。

要求：

- 只改表达，不改事实和剧情。
- 修改前创建快照；修改后重新进入审计链。
- 修订记录写入工作区 `novel_state.json` 的 `revision_history`。
