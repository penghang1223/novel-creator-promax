---
description: 新书立项：平台、题材、设定、大纲、细纲与 seal 门禁
argument-hint: "[平台] [题材/创意]"
---

读取并执行 `${CLAUDE_PLUGIN_ROOT}/skills/novel-project-planning/SKILL.md`。

要求：

- 新项目目录位于 `${CLAUDE_PROJECT_DIR}/novel_output/{平台}/{书名}`。
- 完成 `project_bootstrap_pipeline.py init` 后，按清单补齐资料，再运行 `seal`。
- `seal` 未通过时，不要进入第 1 章正文。

## 阶段记录

`seal` 通过后：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/workflow.py" --workspace "${CLAUDE_PROJECT_DIR}" \
  advance --to init --novel-dir "${CLAUDE_PROJECT_DIR}/novel_output/{平台}/{书名}"
```
