---
name: novel-memory
description: 长篇小说记忆系统的初始化、唤醒、章节回填、阶段体检和紧急修复。用户说“记忆”“别吃设定”“同步记忆”“回顾前文”时使用。只维护记忆产物，不改正文。
---

# 小说记忆

读取并严格执行：

1. `${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/novel-memory-pro/SKILL.md`
2. `${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/MODE_REGISTRY.md` 的 `memory` 模式

## 边界

- 只写工作区 `记忆/`、`摘要/` 和 `.claude/memory/`。
- 不修改正文、passport 或 commit。
- 记忆回填失败时不得推进下一章。
- 项目进度同步到 `${CLAUDE_PROJECT_DIR}/knowledge_base/80_Projects/`。
