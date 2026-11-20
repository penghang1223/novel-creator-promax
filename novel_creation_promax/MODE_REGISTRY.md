# Mode Registry

> 本文件是小说创作 Pro Max 的功能编号与触发规则唯一真源。`skills/novel-creator/SKILL.md`、`AGENTS.md`、命令文档只引用本表，不另行维护编号副本。

## 使用规则

- 用户明确选择编号时，按 `mode_id` 执行。
- 用户用自然语言描述任务时，按 `trigger_examples` 匹配模式。
- 如果一个请求同时命中多个模式，按更具体的模式优先：发布 > 审稿 > 润色 > 正文写作 > 大纲/立项。
- 正文写作、润色、审稿、复盘会写入或读取小说项目目录；纯咨询类模式只读知识库，除非用户要求落盘。

## 模式总表

| mode_id | mode_key | 名称 | 典型触发 | entry_type | 必读入口 | 主要产物 | 强制门禁 |
|---:|---|---|---|---|---|---|---|---|
| 0 | onboarding | 新手立项 | 从零写、帮我立项、新书 | skill | `skills/novel-project-planning/SKILL.md` | 创意/设定/结构/细纲 | bootstrap gate |
| 1 | free-create | 自由创作 | 写个故事、来一篇短故事 | doc | `references/trigger-rules.md` + 对应题材知识 | 正文、摘要、outline | 基础审计 |
| 2 | genre-analysis | 题材分析 | 这个题材怎么样、分析赛道 | kb | `knowledge_base/10_WorldBuilding/题材知识库/` | 题材分析报告 | 无 |
| 3 | idea-classify | 创意归类 | 这个点子适合哪个平台/题材 | kb | `knowledge_base/60_Platform/平台规则.md` | 创意归类建议 | 创意评分可选 |
| 4 | outline | 大纲生成 | 生成大纲、分卷、细纲 | skill | `skills/novel-project-planning/SKILL.md` | 大纲、分卷、细纲 | 结构评估 |
| 5 | chapter-write | 正文写作 | 写第N章、续写、下一章 | doc | `references/orchestrator.md` Stage 5 + `skills/novel-chapter-write/SKILL.md` | 正文、摘要、passport、taskbook、review JSON | pre-check、未知事实、gate、结构化审稿、audit |
| 6 | style | 风格定制 | 模仿风格、调语气、毒舌风 | kb | `knowledge_base/40_Writing/风格指南/风格索引.md` | style_dna 或风格约束 | 风格校准 |
| 7 | memory | 记忆管理 | 查看记忆、同步记忆、别吃设定 | skill | `skills/novel-memory/SKILL.md` | memory JSON、review pack | schema 校验 |
| 8 | polish | 正文润色 | 润色、降AI、改对话、调节奏 | kb | `knowledge_base/40_Writing/05_降AI痕迹/降低AI痕迹.md` | 修订稿、revision_history | 审计复跑 |
| 9 | review | 审稿评估 | 审一下、质量怎么样、帮我看看 | skill | `skills/novel-review/SKILL.md` + `references/review-result-schema.md` | 审稿 JSON、人读报告 | 自动审计先跑、reviewer 契约 |
| 10 | short-story | 短篇创作 | 短篇、知乎盐选、短故事 | doc | `references/trigger-rules.md` | 短篇正文、摘要 | 字数/结构审计 |
| 11 | platform-output | 多平台输出 | 番茄格式、起点格式、发布同步 | skill | `skills/novel-publish/SKILL.md` | 平台稿、同步结果 | 平台规则检查 |
| 12 | retrospective | 完结复盘 | 完结复盘、总结教训、升级规则 | script | `novel_creation_promax/scripts/novel_review_and_upgrade.py` | 复盘报告、规则建议 | 用户确认后入库 |
| 13 | continuation | 续写他人作品 | 续写这篇、接着这个风格写 | script | `skills/novel-memory/scripts/style_dna_extractor.py` | 风格DNA、续写正文 | 风格校准 |
| 14 | market-research | 平台热门方向调研 | 最近什么题材火、平台榜单、市场调研 | skill | `skills/novel-market-research/SKILL.md` | 市场调研报告 | 来源与日期标注 |
| 15 | idea-generation | 创意生成 | 给我几个选题、脑洞、创意方案 | skill | `skills/novel-idea/SKILL.md` | 创意卡、五维评分 | 五维评分 + 差异化检查 |
| 16 | workflow | 工作流阶段 | 工作流到哪了、下一步做什么、阶段门禁 | skill | `skills/novel-workflow/SKILL.md` | workflow.json、阶段状态 | 阶段门禁 |
| 17 | data-diagnosis | 数据诊断 | 我扑了、数据掉了、断流、要不要切书、书测 | skill | `skills/novel-diagnose/SKILL.md` + `tools/data_diagnosis.py` | 诊断报告、七天动作 | 11 项数据完整 |

## 模式执行要点

### 0. 新手立项

从零开始写长篇时，必须先创建并封存项目门禁；未通过门禁不得写第1章。

```bash
python novel_creation_promax/scripts/project_bootstrap_pipeline.py init --platform "{平台}" --title "{书名}" --genre "{题材}" --premise "{核心设定}"
python novel_creation_promax/scripts/project_bootstrap_pipeline.py seal --novel-dir "novel_output/{平台}/{书名}"
```

`seal` 会检查共享记忆、4个必读知识库、项目目录、`project_bootstrap.json`、风格DNA、总纲、8卷细纲、`素材/小说信息.md`、`80_Projects/_config.md`、`MEMORY.md`。只有 `novel_state.json.workflow_gate.can_write_chapter=true` 时，正文流水线才允许运行。

### 5. 正文写作

必须按 `references/orchestrator.md` 的 Stage 5 执行。推荐命令：

```bash
python novel_creation_promax/scripts/write_pipeline.py pre --novel-dir "{小说目录}" --chapter N --title "{标题}"
python novel_creation_promax/scripts/write_pipeline.py post --novel-dir "{小说目录}" --chapter N --title "{标题}"
```

交付前必须具备：

- 章节正文文件
- `摘要/chapter_NNN_rule_stack.json` 的 `write_ready=true`（无 critical 未知事实）
- `rule_stack.truth_layers` 区分作者真相 / 读者已知 / 未揭示事实
- `摘要/chapter_NNN_taskbook.md`（context-agent 五段任务书）
- `writing_gate.py` 通过
- 写后审计通过或明确列出未通过项
- `摘要/chapter_NNN_review.json`（reviewer 契约；tribunal 模式必填）
- `摘要/chapter_NNN_passport.json`
- 若有章节摘要，则同步到 `记忆/`

审稿存在 `blocker` 时，`post --phase quality` 和 `commit` 会阻断。

### 8. 正文润色

润色不允许只改聊天窗口内容。必须读取原章节文件，输出修订稿或覆盖前备份，并更新 `novel_state.json.revision_history`。润色后至少重跑 `novel_creation_promax/scripts/post_write_audit.py`。

### 9. 审稿评估

基础审计自动执行；深度审稿由用户触发或基础审计问题较多时建议进入。深度审稿使用 `skills/novel-review/SKILL.md`，不要把它和硬规则审计混为一谈。

1. 运行 `post_write_audit.py` 获取硬规则证据。
2. 调用 `reviewer` 子代理，只返回五维 JSON。
3. 用 `tools/review_result.py save` 校验并写入 `摘要/chapter_NNN_review.json`。
4. 用 `tools/review_result.py status` 查看 blocking，`render` 生成人读报告。
5. `blocker` 必须修复；quality 与 commit 会阻断。
6. 审稿通过 `target`、`basis` 和 `expected_versions` 绑定正文与输入；正文、rule_stack、taskbook、memory_pack 或流程版本变化后变为 `stale`，必须重新审稿。

### 12. 完结复盘

自动升级知识库规则前必须先给出建议清单，等待用户确认。确认后才可写入 `knowledge_base/`。

### 14. 平台热门方向调研

先确认平台和时间窗口；平台未定先问，不要默认番茄。基线读 `knowledge_base/60_Platform/`，联网结论必须带 URL 和访问日期；无法联网时标注“仅知识库基线”。报告写入工作区 `素材/调研/`，结论必须落到可执行选题。

### 15. 创意生成

先读同平台调研报告和创意五维评分；没有调研报告时说明基于知识库基线生成。一次最多 10 个，默认 5 个，至少覆盖 3 种核心情绪/爽点。每个创意用 `tools/idea_score.py` 评分，低于 60 不得推荐立项；用户选定后交给立项流程。

### 16. 工作流阶段

`workflow.py` 只负责项目级外层导航：调研 → 创意 → 立项 → 写章 → 发布。阶段顺序默认不可跳；跳阶段必须 `--force --reason` 并写入 `overrides`。它不替代 `seal`、`writing_gate`、`post_write_audit` 或章节 commit。

### 17. 数据诊断

上线后先要齐 11 项数据，再运行 `tools/data_diagnosis.py`。缺数据不给处方；七天里只动一件事；先修最前端。
