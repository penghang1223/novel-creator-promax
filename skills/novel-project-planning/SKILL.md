---
name: novel-project-planning
description: 新书立项、世界观与人物设定、长篇大纲、分卷和章节细纲。用户说“立项”“新书”“设定”“生成大纲”“分卷”“细纲”时使用。负责 bootstrap/seal 交接，不写正文。
---

# 小说立项与规划

读取并严格执行：

1. `${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/project-planning/SKILL.md`
2. `${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/MODE_REGISTRY.md` 的 `onboarding` / `outline` 模式
3. `${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/references/orchestrator.md` 中立项与大纲阶段

## 边界

- 只产出创意、设定、结构、细纲和立项门禁报告。
- 不写章节正文。
- 新项目目录必须位于 `${CLAUDE_PROJECT_DIR}/novel_output/{平台}/{书名}`。
- 立项完成后必须运行 `seal`；未通过不得进入写章流水线。

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/scripts/project_bootstrap_pipeline.py" init \
  --platform "番茄" --title "书名" --genre "题材" --premise "核心设定"
python3 "${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/scripts/project_bootstrap_pipeline.py" seal \
  --novel-dir "${CLAUDE_PROJECT_DIR}/novel_output/番茄/书名"
```
