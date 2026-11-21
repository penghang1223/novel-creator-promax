---
name: novel-revision
description: 改稿与润色。用户说“润色”“改稿”“重写这段”“降AI”“调整节奏”“修对话”“改开头”时使用。保护原稿、记录修订历史、改后重跑审计；只要求审稿时用 novel-review。
---

# 改稿与润色

## 边界

| 拥有 | 不拥有 |
|---|---|
| 用户授权范围内的正文修订、备份、修订记录 | 审稿授权、发布授权、设定与核心结局的越权修改 |

- 审稿结论不是自动修改授权；用户明确说“修、润色、重写”后才进入本技能。
- 只处理任务范围；未授权结构修改时，保留情节、结局和人物动机。
- 正文变化会使旧 commit 失效，必须重新走审计链，不能手动标记通过。

## 工作区确认

写入前运行：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/workspace.py" --workspace "${CLAUDE_PROJECT_DIR}" status --json
```

`dangerous=plugin_root|root` 时停止；未确认且无存量书时先让用户确认产物目录。

## 执行

1. **明确范围**：读目标正文、相邻章节、相关细纲和设定，以及用户反馈；判断是词句润色、场景修改还是结构重构。
2. **可选审稿**：需要问题清单时调用 `${CLAUDE_PLUGIN_ROOT}/skills/novel-review/SKILL.md`。按剧情逻辑 → 人物一致 → 节奏 → 词句的顺序处理；单纯词句润色不强制全套深审。
3. **先保存原稿**：
   - 有章节编号：用 `tools/revision_queue.py snapshot/propose/review`，不能绕过基线指纹检查。
   - 无章节编号的独立短篇：在 `素材/备份/` 保存带时间与内容指纹的原稿，并记录对应正文路径。
4. **只改任务范围**：涉及细纲实质偏离时，按 `novel_creation_promax/references/orchestrator.md` 的偏离协议先说明并获得确认，再更新相关规划与变更记录。
5. **重跑审计**：正文变化后清除对应旧章节 commit，重新执行 `write_pipeline.py post`（audit → truth → quality → memory → commit）。使用修改工具时先确认它是否已处理凭证失效。
6. **记录修订**：在 `novel_state.json` 的 `revision_history` 写入时间、范围、原因、备份位置、验证结果；剧情事实变化通过 truth delta 和记忆流程回填，并同步 `knowledge_base/80_Projects/`。
7. **交付**：给出修订稿路径、关键变化、验证结论和未解决问题；不要只在聊天里展示片段就声称文件已修改。

## 命令

```bash
# 修改前快照
python3 "${CLAUDE_PLUGIN_ROOT}/tools/revision_queue.py" snapshot \
  --novel-dir "{小说目录}" --chapter N --reason "修改前备份"

# 提案式修改（不直接覆盖正文）
python3 "${CLAUDE_PLUGIN_ROOT}/tools/revision_queue.py" propose \
  --novel-dir "{小说目录}" --chapter N --content-file /tmp/proposed.md --reason "润色"

# 审批后重新走审计链
python3 "${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/scripts/write_pipeline.py" post \
  --novel-dir "{小说目录}" --chapter N --title "{标题}"
```

## 硬规则

- 先备份再修改；不覆盖别人随后修改的基线。
- 旧审计报告不能当新稿通过证据；正文变了就必须重跑。
- 不机械清零常用词，不破坏自然度、人物声纹和证据链。
- 剧情事实变化必须回填 truth delta 与记忆，不能只改正文。
- 独立短篇按 `short-story-workflow.md` 的审计适用边界执行，不套用长篇固定字数阈值。
- 修改后不自动发布；发布仍走独立授权入口。

## 禁止事项

- 不无备份覆盖正文。
- 不把审稿结论当成修改授权，不越权改变设定和核心结局。
- 不伪造 commit、审计通过或 revision 记录。
- 不因“降 AI”破坏人物声纹、逻辑链或已有伏笔。
- 不在未获授权时做结构重构或改结局。
