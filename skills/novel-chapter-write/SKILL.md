---
name: novel-chapter-write
description: 写章、续写、短篇创作和正文润色。用户说“写第N章”“续写”“下一章”“润色这章”时使用。强制执行写前检查、Pass 1、门禁、Pass 2、结构化审稿、审计、真相回填和 commit。
---

# 小说正文写作

读取并严格执行：

1. `${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/references/orchestrator.md` 的 Stage 5
2. `${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/MODE_REGISTRY.md` 的 `chapter-write` / `polish` 模式
3. `${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/references/knowledge-pack-workflow.md`

## 强制流程

0. 检查工作区确认状态：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/workspace.py" --workspace "${CLAUDE_PROJECT_DIR}" status --json
```

`dangerous=plugin_root|root` 时停止；`confirmed=false` 且 `legacy_books=0` 时先让用户确认产物目录，再继续。

1. 读本章细纲 + 上一章正文 + 工作区记忆包。
2. 运行 `write_pipeline.py pre` 生成知识包、记忆包、9 问和章节骨架。若 `rule_stack.write_ready=false`，先补齐真相文件 `open_questions`，不得进入下一步。
3. 调用子代理 `novel-creator-pro:context-agent`，生成五段写作任务书，写入 `摘要/chapter_NNN_taskbook.md`。人物段只能使用 `rule_stack.truth_layers.reader_known` 和 `character_knowledge`；未揭示事实只能作为作者计划。任务书缺失或返回 blocker 时，先补齐细纲/设定，不得直接起草。
4. **只依据任务书起草 Pass 1 剧情稿**（不管 AI 词，截断点停笔）。
5. 运行 `writing_gate.py`；不通过先修 Pass 1。
6. 写 **Pass 2 去 AI 稿**（只改词汇，不动叙事）。
7. 先用 `target --with-basis` 取正文哈希和审稿依据，调用 `novel-creator-pro:reviewer` 时要求它把 `target`、`basis`、`expected_versions` 原样写进 JSON；再用 `save` 校验并写入 `摘要/chapter_NNN_review.json`，最后渲染人读报告：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/review_result.py" target \
  --novel-dir "${CLAUDE_PROJECT_DIR}/novel_output/番茄/书名" --chapter N --json --ensure-revision --with-basis
python3 "${CLAUDE_PLUGIN_ROOT}/tools/review_result.py" save \
  --novel-dir "${CLAUDE_PROJECT_DIR}/novel_output/番茄/书名" --chapter N --input /tmp/reviewer.json
python3 "${CLAUDE_PLUGIN_ROOT}/tools/review_result.py" render \
  --novel-dir "${CLAUDE_PROJECT_DIR}/novel_output/番茄/书名" --chapter N \
  --output "${CLAUDE_PROJECT_DIR}/novel_output/番茄/书名/素材/审稿报告_chNNN.md"
```

8. 运行 `write_pipeline.py post`：审计 → 真相 → 质量（含结构化审稿门禁）→ 记忆 → commit。

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/scripts/write_pipeline.py" pre \
  --novel-dir "${CLAUDE_PROJECT_DIR}/novel_output/番茄/书名" --chapter N --title "标题"
python3 "${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/scripts/write_pipeline.py" post \
  --novel-dir "${CLAUDE_PROJECT_DIR}/novel_output/番茄/书名" --chapter N --title "标题"
```

## 可选：深度事实提取

如果本章新增人物、势力、规则或伏笔较多，可调用 `novel-creator-pro:data-agent` 生成 `truth_delta` 草案。主流程写入 `摘要/chapter_NNN_truth_delta.json` 后，仍必须通过：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/scripts/story_truth_manager.py" validate-delta \
  --novel-dir "{小说目录}" --chapter N
python3 "${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/scripts/story_truth_manager.py" apply-delta \
  --novel-dir "{小说目录}" --chapter N
```

## 可选强化技能

以下技能随插件分发，按需调用，不替代上面的强制流程：

- `deai-check`：Pass 2 前诊断 AI 味，按五层顺序改写。
- `chapter-hook`：起草前确认章末截断点与钩型轮换，写后复查章尾形态。

## 红线

- 9 问评分 < 70 不得动笔。
- 证据分级：Pass 1 只能使用 `confirmed` 事实；`inferred` 必须标明依据；`assumed` 一律回到 pre 补齐，不得写进正文。
- 细纲偏离必须先向用户说明并获得确认。
- reviewer 返回的 JSON 不得手工伪造；契约校验失败必须重新审查。
- 审稿存在 `blocker` 时，quality 与 commit 阶段会阻断，不得绕过。
- 正文、摘要、passport、commit 只写工作区，禁止写入插件目录。
- 写完后运行完整性校验：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/verify_project_integrity.py" \
  --novel-dir "${CLAUDE_PROJECT_DIR}/novel_output/番茄/书名"
```
