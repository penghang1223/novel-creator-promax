---
name: novel-chapter-write
description: 写章、续写、短篇创作和正文润色。用户说“写第N章”“续写”“下一章”“润色这章”时使用。强制执行写前检查、Pass 1、门禁、Pass 2、审计、真相回填和 commit。
---

# 小说正文写作

读取并严格执行：

1. `${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/references/orchestrator.md` 的 Stage 5
2. `${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/MODE_REGISTRY.md` 的 `chapter-write` / `polish` 模式
3. `${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/references/knowledge-pack-workflow.md`

## 强制流程

1. 读本章细纲 + 上一章正文 + 工作区记忆包。
2. 运行 `write_pipeline.py pre` 生成知识包、记忆包、9 问和章节骨架。
3. 生成场景写作卡，写 **Pass 1 剧情稿**（不管 AI 词，截断点停笔）。
4. 运行 `writing_gate.py`；不通过先修 Pass 1。
5. 写 **Pass 2 去 AI 稿**（只改词汇，不动叙事）。
6. 运行 `write_pipeline.py post`：审计 → 真相 → 质量 → 记忆 → commit。

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/scripts/write_pipeline.py" pre \
  --novel-dir "${CLAUDE_PROJECT_DIR}/novel_output/番茄/书名" --chapter N --title "标题"
python3 "${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/scripts/write_pipeline.py" post \
  --novel-dir "${CLAUDE_PROJECT_DIR}/novel_output/番茄/书名" --chapter N --title "标题"
```

## 红线

- 9 问评分 < 70 不得动笔。
- 细纲偏离必须先向用户说明并获得确认。
- 正文、摘要、passport、commit 只写工作区，禁止写入插件目录。
- 写完后运行完整性校验：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/verify_project_integrity.py" \
  --novel-dir "${CLAUDE_PROJECT_DIR}/novel_output/番茄/书名"
```
