---
description: 把章节转成动漫分镜、角色/场景提示词和 Sora/即梦分镜
argument-hint: "[书名] [第N章|章节范围] [画风]"
---

读取并执行 `${CLAUDE_PLUGIN_ROOT}/skills/anime-storyboard/SKILL.md`。

要求：

- 只读正文与设定，不改正文。
- 产物写入 `${CLAUDE_PROJECT_DIR}/素材/分镜/{书名}/`。
- 角色外观以 `设定/人物档案.md` 和 `设定/真相文件/characters.json` 为准；缺失项标“原文未描述”，不要编造。
- 输出角色形象、角色提示词、场景提示词、`sora_分镜.json` 和分镜表。
