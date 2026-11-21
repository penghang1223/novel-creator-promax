# Pipeline

> 本文是流水线速查。完整裁决规则见 `references/orchestrator.md`。

## 总流程

| 阶段 | 输入 | 动作 | 输出 | Gate |
|---|---|---|---|---|
| 立项门禁 | 用户确认的书名/平台/题材/核心设定 | `project_bootstrap_pipeline.py init` → 补齐资料 → `seal` | `素材/project_bootstrap_gate.json` | `can_write_chapter=true` |
| 创意 | 用户想法 | 题材/平台/卖点评估 | 创意文档 | 五维评分 |
| 设定 | 创意文档 | 人物、地点、势力、事件、关系、常识约束、能力、伏笔 | 设定目录+真相文件 | 设定底座+真相文件+12项完整性 |
| 大纲 | 设定 | 雪花级联、主支线 | 结构/总大纲 | 结构评估 |
| 细纲 | 大纲 | 分卷、章节节点 | 细纲文件 | 节奏/伏笔检查 |
| 正文 | 细纲+记忆包 | Pass 1/2 写作 | 章节正文 | pre/gate/audit |
| 记忆 | 章节摘要 | 回填状态变化 | 记忆 JSON | schema |
| 复盘 | 全书/阶段内容 | 总结问题和规则 | 复盘报告 | 用户确认 |

## 从零开始长篇

从零写长篇时，先跑立项门禁。`init` 只创建结构和占位文件，不允许正文；`seal` 负责最终复核。

```bash
python novel_creation_promax/scripts/project_bootstrap_pipeline.py init --platform "{平台}" --title "{书名}" --genre "{题材}" --premise "{核心设定}"
python novel_creation_promax/scripts/project_bootstrap_pipeline.py seal --novel-dir "novel_output/{平台}/{书名}"
```

`seal` 通过后会写入：

```json
{
  "workflow_gate": {
    "bootstrap_status": "pass",
    "bootstrap_report": "素材/project_bootstrap_gate.json",
    "last_checklist_step": 20,
    "can_write_chapter": true
  }
}
```

`write_pipeline.py pre/post/all` 会先读取这个状态；缺失或失败时直接退出。

`seal` 还会强制检查设定底座：`人物档案.md`、`地点档案.md`、`势力档案.md`、`事件档案.md`、`关系网络.md`、`常识约束.md`。这些文件用于锁定人物行为、居住收入、组织边界、事件因果和信息差，避免正文里出现高薪却无解释住老破小、技术强却无原因被裁、角色突然说不符合身份的话。

`seal` 同时检查 `设定/真相文件/` 下 7 个结构化事实源：`characters.json`、`locations.json`、`factions.json`、`events.json`、`relationships.json`、`resources.json`、`foreshadowing.json`。这些文件不是可选资料；它们会被 `write_pipeline.py pre` 编译成每章 `rule_stack`。

## 续写他人作品

外部文本续写使用独立入口，不伪造长篇 `seal`：

```bash
python novel_creation_promax/scripts/continuation_import.py \
  --input "{原文}" --title "{书名}" --platform "{平台}" --genre "{题材}" --confirm-workspace
python novel_creation_promax/scripts/project_bootstrap_pipeline.py \
  continuation-gate --novel-dir "novel_output/{平台}/{书名}" --approve
```

- `continuation_import.py` 拆文、建项目、导入真相文件，但保持 `can_write_chapter=false`。
- `continuation-gate --approve` 在用户审查报告后写入 `素材/continuation_import_gate.json`，设置 `bootstrap_status=continuation_import` 与 `can_write_chapter=true`。
- 真相文件校验在 `import_mode=continuation` 下允许部分类别为空，但已有记录仍必须无占位词、字段完整。
- 章节号衔接原文最后一章，首章仍必须 `pre → post`。

## 每章强制流程

1. 校验真相文件，并生成章节记忆包。
2. 按 `knowledge_base/_ROUTES.json` 生成 `摘要/chapter_NNN_knowledge_pack.json`：`required` 五项 + 按章节号、标题和**细纲场景标签**选中的路由；`retrieval` 只检索 `20_Characters` / `30_Plot` / `40_Writing`，避免项目元数据污染。
   `required` 或 `selected_routes` 存在缺失文件时，默认记为 `knowledge_pack=warning` 并逐项打印；设置 `novel_state.json` 的 `knowledge_gate="strict"` 或运行 `pre --strict-knowledge` 时改为阻断。
3. 编译 `摘要/chapter_NNN_rule_stack.json` 和 `素材/chapter_NNN_truth_brief.md`；rule_stack 会列出 `unknown_facts`、`assumed_facts`、`evidence_policy`、`write_ready` 和 `truth_layers`（作者真相 / 读者已知 / 未揭示事实），并生成 `追踪/时间线/` 派生视图。`active_rules` 的事实分 `confirmed / inferred / assumed` 三级，`assumed` 禁止进入正文。
4. 调用 `novel-creator-pro:context-agent` 生成五段写作任务书，写入 `摘要/chapter_NNN_taskbook.md`；返回 blocker 时先补细纲或设定。
5. 回答 9 问并运行 `novel_creation_promax/scripts/pre_write_check.py`；存在 critical `unknown_facts` 或 critical `assumed_facts` 时直接阻断。
6. 按 rule_stack 和任务书组装场景写作卡。
7. 写 Pass 1 剧情稿。
8. 运行 `novel_creation_promax/scripts/writing_gate.py`。
9. 写 Pass 2 去AI稿。
10. 先用 `tools/review_result.py target --ensure-revision --with-basis` 取正文哈希、revision 和审稿依据，调用 `novel-creator-pro:reviewer` 产出带 `target`、`basis`、`expected_versions` 和 `source_refs` 的 `摘要/chapter_NNN_review.json`，再用 `validate` 校验并 `render` 人读报告。
11. `post` 自动提取 `素材/truth_delta_candidates_chNNN.json|md`，先审查候选事实，再补齐 `摘要/chapter_NNN_truth_delta.json`。
12. 运行 `novel_creation_promax/scripts/post_write_audit.py`；第 1-3 章同时运行 `tools/opening_score.py`。
13. 运行字数归一化、truth delta、风格校准和人物一致性检查。
14. 生成章节摘要和 chapter passport，回填 `novel-memory`、真相文件和 `novel_state.json`；同时重建 `追踪/情绪账.md`。
15. 所有必需检查通过后生成 `素材/commits/chapter_NNN.commit.json`，用 SHA-256 绑定正文、passport、audit、truth delta、review 和检查报告；后续章节门禁会校验这条提交记录。

推荐命令：

```bash
python novel_creation_promax/scripts/write_pipeline.py pre --novel-dir "{小说目录}" --chapter N --title "{标题}"
python novel_creation_promax/scripts/write_pipeline.py post --novel-dir "{小说目录}" --chapter N --title "{标题}"
```

`post` 已拆成可断点重跑的阶段：

```bash
python novel_creation_promax/scripts/write_pipeline.py post --novel-dir "{小说目录}" --chapter N --phase audit
python novel_creation_promax/scripts/write_pipeline.py post --novel-dir "{小说目录}" --chapter N --phase truth
python novel_creation_promax/scripts/write_pipeline.py post --novel-dir "{小说目录}" --chapter N --phase quality
python novel_creation_promax/scripts/write_pipeline.py post --novel-dir "{小说目录}" --chapter N --phase memory
python novel_creation_promax/scripts/write_pipeline.py post --novel-dir "{小说目录}" --chapter N --phase commit
```

不指定 `--phase` 时仍执行全部阶段，保持旧命令兼容。每个阶段会更新 `摘要/chapter_NNN_passport.json.workflow` 和 `novel_state.json.resume_point`；同一章节同时只允许一个进程运行，锁文件位于 `素材/runs/chapter_NNN.lock`。

状态顺序为 `pre → draft → audit → truth → quality → memory → commit`。失败时不回滚已通过阶段，按 `resume_point.action` 重跑对应阶段即可。

平台档案统一维护在 `knowledge_base/60_Platform/_PROFILES.json`。`writing_gate` 会在 audit 阶段生成 `素材/platform_preflight_chNNN.json`，记录平台、字数门禁和推荐区间；平台规则变化时只改档案，不再修改脚本常量。

`post` 如果发现正文低于 2800，会生成 `素材/chapter_NNN_normalizer_task.md`，列出必须补写的观察、试探、交锋、代价、新线索位置。不能用水景物、复述、空泛心理凑字。

每个外部检查子流程都会追加到 `素材/runs/pipeline_runs.jsonl`，记录章号、命令、耗时、返回码和截断后的输出。CLI 或 dashboard 重启后仍可按章追查失败步骤。

下一章 `pre` 会检查上一章 passport 中的 `pipeline.post_write_audit`，不再因为存在 audit 文件就放行。历史补流程可临时使用 `--override-prev-audit`。

`chapter_guard.py --changed-only` 默认对缺少 commit 的存量章节给出警告；新流程可加 `--require-commit`，把提交记录缺失或指纹失配升级为阻断。

跨项目债务扫描：

```bash
python tools/quality_debt.py --output novel_output/_workspace/reports/quality_debt.json
python tools/quality_debt.py --novel-dir "{小说目录}" --json
```

报告集中列出 override 未偿还、章节工作流阻塞、流水线未完成、commit 缺失和真相候选待复核，不自动修改正文或状态。

SQLite 读模型同步：

```bash
python tools/sync_story_index.py
python tools/sync_story_index.py --json
python tools/sync_story_index.py --check
```

索引文件位于 `novel_output/_workspace/index/story_index.sqlite3`。它只缓存项目、章节、passport、工作流和 commit 的查询字段；删除章节或项目后再次同步会删除对应索引记录。

正文修改保护：

```bash
python tools/revision_queue.py snapshot --novel-dir "{小说目录}" --chapter N --reason "修改前备份"
python tools/revision_queue.py propose --novel-dir "{小说目录}" --chapter N --content-file /tmp/proposed.md --reason "模型润色"
python tools/revision_queue.py list --novel-dir "{小说目录}" --chapter N
python tools/revision_queue.py review --novel-dir "{小说目录}" --chapter N --proposal-id "提案ID" --approve
```

proposal 不会直接覆盖正文；审批时会检查基线 SHA-256，正文已变化则标记为 `stale`。Dashboard 直接编辑会先创建快照，并清除旧 commit，要求重新执行 post。

场景级 passport 是可选门禁：

```bash
python tools/scene_passport.py init --novel-dir "{小说目录}" --chapter N --plan-file scene_plan.json
python tools/scene_passport.py update --novel-dir "{小说目录}" --chapter N --scene 1 --status pass
python tools/scene_passport.py list --novel-dir "{小说目录}" --chapter N
```

只有启用了场景计划的章节，commit 才会要求全部场景为 `pass`；历史章节无 `scene_index` 时保持原流程。

质量模式：

```bash
python novel_creation_promax/scripts/write_pipeline.py post --novel-dir "{小说目录}" --chapter N --quality-mode deterministic
python novel_creation_promax/scripts/write_pipeline.py post --novel-dir "{小说目录}" --chapter N --quality-mode balanced
python novel_creation_promax/scripts/write_pipeline.py post --novel-dir "{小说目录}" --chapter N --quality-mode tribunal --quality-review-report review.json
```

`deterministic` 是默认兼容模式；`balanced` 允许附加审稿但不强制；`tribunal` 必须提供 `status=pass` 的人工确认报告，才允许 commit。

Dashboard 提供 `/api/insights/index` 和 `/api/insights/quality-debt`，展示索引项目数、章节状态和质量债务摘要。

知识库检索索引：

```bash
python tools/knowledge_search.py --sync-only
python tools/knowledge_search.py "高压 对话 张力" --limit 8 --backend lexical
python tools/knowledge_search.py "高压 对话 张力" --limit 8 --backend tfidf
```

索引位于 `novel_output/_workspace/index/knowledge_index.sqlite3`，只作为可重建的检索读模型；原始 Markdown/JSON 仍是唯一真源。章节 `knowledge_pack` 会自动附带 `retrieval` 结果，默认使用 BM25 并按选中路由的技法目录加权，也可在 `novel_state.json` 设置 `retrieval_backend: "lexical" | "tfidf"`。

张力曲线契约：在项目 `novel_state.json` 中启用后，章节摘要的 `chapter_metrics.tension_curve` 使用 1-10 数值数组；quality 和 commit 阶段会要求满足峰值、点数和结尾释放规则。

```bash
python tools/tension_curve.py --novel-dir "{小说目录}" --chapter N
python tools/backfill_tension.py --root . --apply
```

`backfill_tension.py` 只在 `素材/tension/` 生成 `source=heuristic` 的估算报告，不修改正文、摘要或审计状态；估算结果仅用于趋势看板，不会被当作人工审稿通过。

结构契约校验：

```bash
python tools/validate_contracts.py --novel-dir "{小说目录}" --chapter N
```

`post` 还会先运行 `story_truth_manager.py extract-delta`。如果正文出现人物状态、关系、地点、势力、资源、伏笔等疑似变化，会写入 `truth_delta.auto_extraction`，并把 `review_status` 设为 `needs_review`。必须审查 `素材/truth_delta_candidates_chNNN.md`，把属实项写入 `chapter_observations/proposed_updates`，再把 `auto_extraction.review_status` 改为 `reviewed` 并填写 `review_note`；否则 truth delta 校验不通过。

## 单一写者与状态一致性

只有以下脚本能写状态文件：

- `write_pipeline.py`：passport、`novel_state.json`、commit
- `project_bootstrap_pipeline.py`：立项门禁与 `novel_state.workflow_gate`
- `story_truth_manager.py`：真相文件与 truth delta

skill、子代理和域包只能读；`guard_runtime_write.py` 会拦截直接写入。`verify_project_integrity.py` 负责交叉校验：

- `resume_point` / `novel_state.chapters[].workflow` / `passport.workflow` 三者一致
- commit 必须绑定 `chapter` / `passport` / `audit` / `truth_delta` 四类产物
- commit 中所有产物的 SHA-256 必须与磁盘一致
- review 的 `target.sha256` 必须与正文一致；`stale` / `blocked` / `invalid` 不得存在 accepted commit
- `rule_stack.write_ready=false`、存在 critical 未知事实或 critical `assumed_facts` 时，正文不得存在

交付前运行：

```bash
python3 tools/verify_project_integrity.py --novel-dir "{小说目录}" --json --strict
```

## 失败处理

| 失败项 | 处理 |
|---|---|
| 9问低于70 | 补全本章目标、冲突、伏笔、截断点后重跑 |
| Gate 不通过 | 修 Pass 1，不进入去AI |
| 字数不达标 | 扩写有效剧情，不水重复信息 |
| AI词/乒乓句超标 | 定点修，不破坏剧情结构 |
| 风格漂移 | 参照 style DNA 修局部语感 |
| OOC 风险 | 回看人物档案，修动机和声纹 |
| 记忆回填失败 | 不推进下一章，先修摘要或 schema |
| 知识包缺失 | 默认 warning；`knowledge_gate=strict` 或 `--strict-knowledge` 时阻断，先补文件或移除失效路由 |
