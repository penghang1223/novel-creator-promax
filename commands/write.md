---
description: 写一章或续写下一章，强制走完整写章流水线
argument-hint: "[书名] 第N章 [标题]"
---

读取并执行 `${CLAUDE_PLUGIN_ROOT}/skills/novel-chapter-write/SKILL.md`。

执行顺序：

1. `write_pipeline.py pre`
2. Pass 1 剧情稿
3. `writing_gate.py`
4. Pass 2 去 AI 稿
5. `write_pipeline.py post`
6. `verify_project_integrity.py`

正文、摘要、passport、commit 只写工作区。

## 阶段记录

首章 commit 生成后：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/workflow.py" --workspace "${CLAUDE_PROJECT_DIR}" \
  advance --to write --novel-dir "${CLAUDE_PROJECT_DIR}/novel_output/{平台}/{书名}"
```
