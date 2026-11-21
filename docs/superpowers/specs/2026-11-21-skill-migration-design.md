# 四个外部技能迁移设计

- 日期：2026-11-21
- 状态：已实施，`bash tools/ci.sh` 通过（286 tests，24 evals）
- 来源：`novel-creator-pro/novel_creation_promax/{short-story,creative-research,manuscript-revision,work-continuation}`

## 1. 背景与结论

来源仓库是全量仓库，子技能放在 `novel_creation_promax/{name}/SKILL.md`；当前插件是精简版，技能发现层是 `skills/{name}/SKILL.md`。两者布局不兼容，不能直接复制。

| 来源技能 | 结论 | 处理方式 |
|---|---|---|
| `short-story` | 值得迁移 | 新建 `skills/novel-short-story/`，并移植 `references/short-story-workflow.md` |
| `manuscript-revision` | 值得迁移 | 新建 `skills/novel-revision/`，`/polish` 改为路由到它 |
| `creative-research` | 只合并增量 | 并入现有 `skills/novel-market-research/`，不新增平行技能 |
| `work-continuation` | 合并进现有续写 | 在 `skills/novel-continuation/` 增加“模式 B：片段续写”，不新增平行技能 |

## 2. short-story

新增：

- `novel_creation_promax/references/short-story-workflow.md`
- `skills/novel-short-story/SKILL.md`
- `commands/short-story.md`

要点：

- 任务边界：平台、题材、读者、整篇字数、投稿目标、禁区。
- 调研先行；纯练笔或用户明确跳过时记录豁免。
- 先锁结局/谜底，再倒推线索位置。
- `素材/短篇写前检查.md` 是人工检查清单，不冒充 Python 门禁。
- 两遍写作 + 整篇审稿。
- 独立短篇不伪造 `workflow_gate`，不套用长篇 2800–3200 单章阈值；已合法 `seal` 的项目仍走原章节门禁。

路由：

- `MODE_REGISTRY` 模式 10 从 `doc` 改为 `skill`，入口 `skills/novel-short-story/SKILL.md`。
- `_ROUTES.json` 的 `short_story` 路由增加工作流文件。
- `_ROUTING.md`、`trigger-rules.md` 同步。

## 3. manuscript-revision

新增：

- `skills/novel-revision/SKILL.md`
- `commands/polish.md` 改为路由到该技能

要点：

- 三种授权范围：词句润色、场景修改、结构重构。
- 先备份：有章节编号用 `revision_queue.py snapshot/propose/review`；独立短篇在 `素材/备份/` 保存带时间与内容指纹的副本。
- 修改后旧 commit 失效，必须重跑 `write_pipeline.py post`。
- `novel_state.json.revision_history` 记录时间、范围、原因、备份位置、验证结果。
- 不自动发布，不越权改设定和核心结局。

路由：

- `MODE_REGISTRY` 模式 8 从 `kb` 改为 `skill`。
- 主技能路由表新增“改稿、润色、降AI、调节奏”。

## 4. creative-research 增量合并

并入 `skills/novel-market-research/SKILL.md`，不新增技能：

- `scope`：short-story / long-project / genre-analysis。
- 复用与更新规则：先查已有报告，平台规则实时核查，不重复无关调研。
- 样本拆解：至少 3 篇不同作品，优先同平台/同题材/近 90 天。
- 来源表：标题、作者或机构、URL、发布日期、访问日期、实际阅读范围。
- 读者反馈与证据限制：区分评论观察与推断，不虚构销量/签约率/转化率。
- 决策落点：至少 3 条“证据 → 判断 → 采用/避开 → 具体落点”。

同时更新 `novel_creation_promax/references/templates/market_research_report.md`，加入来源表、样本拆解、读者反馈、证据限制和决策落点。

## 5. work-continuation 合并

在 `skills/novel-continuation/SKILL.md` 增加两种模式：

| 模式 | 适用 | 入口 |
|---|---|---|
| A. 项目续写 | 原文较长、连续写多章、需要记忆和门禁 | `continuation_import.py` + `continuation-gate` |
| B. 片段续写 | 只给一段/一章，只写接续段 | 续写交接 + 场景卡 + 两遍写作 + 接缝检查 |

新增 `novel_creation_promax/references/templates/continuation_handoff.md`，字段包括：实际阅读范围、最后事件、时间地点、视角时态、在场人物、资源状态、未解冲突、伏笔、未知信息；分列原文事实 / 合理推断 / 拟新增设定；接缝检查覆盖知情范围、动作位置、时间连续、动机声纹、能力限制、未解伏笔。

不新增 `work-continuation` 技能，避免与 `novel-continuation` 抢路由。

## 6. 验证

```bash
bash tools/ci.sh
```

结果：

- 286 tests，0 失败
- 24 skill evals，0 失败
- skill health `errors=0 warnings=0`
- 能力包 3 个，0 错误
- `plugin_doctor` 61 项，0 错误

新增评测：

- `short-story-workflow-contract`
- `revision-backup-audit-contract`
- `continuation-two-modes-contract`

## 7. 非目标

- 不把来源仓库的旧 `novel_creation_promax/{name}/SKILL.md` 布局复制进当前插件。
- 不新增平行的 `creative-research` 或 `work-continuation` 技能。
- 不复制来源仓库的旧 `project-planning`、`review-skill`、`novel-memory-pro` 目录。
