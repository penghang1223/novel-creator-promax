---
description: 润色、改稿、降AI、调整对话与节奏，保护原稿并重跑审计
argument-hint: "[书名] 第N章 [方向]"
---

读取并执行 `${CLAUDE_PLUGIN_ROOT}/skills/novel-revision/SKILL.md`。

要求：

- 先确认修改范围（词句 / 场景 / 结构），未授权结构修改时保留情节、结局和人物动机。
- 先保存原稿：有章节编号用 `revision_queue.py snapshot/propose/review`；独立短篇在 `素材/备份/` 保存带时间和内容指纹的副本。
- 只改任务范围；涉及细纲实质偏离先说明并获得确认。
- 修改后旧 commit 失效，必须重新运行 `write_pipeline.py post`，不得手动标记通过。
- 修订记录写入 `novel_state.json` 的 `revision_history`；剧情事实变化回填 truth delta 与记忆。
