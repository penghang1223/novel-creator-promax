---
description: 续写他人作品：项目续写（拆文建项目）或片段续写（不建项目）
argument-hint: "[原文文件或目录] [书名] [平台] [题材]"
---

读取并执行 `${CLAUDE_PLUGIN_ROOT}/skills/novel-continuation/SKILL.md`。

先判断模式：

- **模式 A 项目续写**：原文较长、要连续写多章、需要记忆和门禁 → 运行 `continuation_import.py`，审查报告，补齐细纲，`continuation-gate --approve` 后写章。
- **模式 B 片段续写**：用户只给一段/一章，只要接着写一段 → 写 `素材/续写交接.md`，提取风格特征，写场景卡，两遍写作，做接缝检查；不建项目。

共同要求：

- 先确认工作区，再写文件。
- 拆文和推断一律标记为推断，不得当作事实写进正文。
- 模式 A 未经 `continuation-gate --approve` 不得写正文。
- 章节号从原文最后一章 + 1 开始（模式 A）。
- 不覆盖原文、不伪造 seal/审计、不自动发布。
