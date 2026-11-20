---
description: 写一章或续写下一章，强制走完整写章流水线（含写作任务书和结构化审稿）
argument-hint: "[书名] 第N章 [标题]"
---

读取并执行 `${CLAUDE_PLUGIN_ROOT}/skills/novel-chapter-write/SKILL.md`。

执行顺序：

1. `write_pipeline.py pre`
2. `context-agent` 生成五段写作任务书
3. Pass 1 剧情稿
4. `writing_gate.py`
5. Pass 2 去 AI 稿
6. `reviewer` 五维 JSON → `tools/review_result.py save` / `render`
7. `write_pipeline.py post`（audit → truth → quality → memory → commit）
8. `verify_project_integrity.py`

审稿存在 `blocker` 时，quality 与 commit 阶段会阻断；不要绕过。
正文、摘要、passport、commit 只写工作区。

## 阶段记录

首章 commit 生成后：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/workflow.py" --workspace "${CLAUDE_PROJECT_DIR}" \
  advance --to write --novel-dir "${CLAUDE_PROJECT_DIR}/novel_output/{平台}/{书名}"
```
