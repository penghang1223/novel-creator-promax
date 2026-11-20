# Artifacts

> 本文规定小说项目产物结构和每章 passport。用于健康检查、流水线和后续发布同步。

## 小说目录结构

长篇项目：

```text
novel_output/{平台}/{小说名}/
├── 创意/
├── 设定/
│   ├── 世界观与人物.md
│   ├── 人物档案.md
│   ├── 地点档案.md
│   ├── 势力档案.md
│   ├── 事件档案.md
│   ├── 关系网络.md
│   ├── 常识约束.md
│   └── 真相文件/
│       ├── characters.json
│       ├── locations.json
│       ├── factions.json
│       ├── events.json
│       ├── relationships.json
│       ├── resources.json
│       └── foreshadowing.json
├── 结构/
├── 细纲/
├── 正文/
├── 摘要/
├── 记忆/
├── 素材/
│   ├── reports/              # 全书审稿、人物扫描等非章节报告
│   ├── state_backups/        # novel_state.json 历史备份
│   ├── revisions/            # 修改前快照和待审批 proposal
│   └── scenes/               # 可选的场景级 passport
│   └── audit_chNNN.json      # 章节审计及流水线产物
├── outline.md
└── novel_state.json
```

长篇立项门禁要求：

```text
记忆/project_bootstrap.json
记忆/style_dna_baseline.json
设定/人物档案.md
设定/地点档案.md
设定/势力档案.md
设定/事件档案.md
设定/关系网络.md
设定/常识约束.md
设定/真相文件/*.json
细纲/卷一.md ... 细纲/卷八.md
素材/小说信息.md
素材/project_bootstrap_gate.json
knowledge_base/80_Projects/{小说名}/_config.md
```

## 设定底座

长篇开写前必须完成设定底座，否则 `project_bootstrap_pipeline.py seal` 不放行正文。

| 文件 | 解决的问题 |
|---|---|
| `设定/人物档案.md` | 人物只有姓名年龄、行为和台词容易 OOC |
| `设定/地点档案.md` | 收入、住所、通勤、消费水平不匹配 |
| `设定/势力档案.md` | 公司、家族、组织、反派资源无边界 |
| `设定/事件档案.md` | 被裁、破产、旧案、事故等事件缺因果链 |
| `设定/关系网络.md` | 谁信谁、谁骗谁、谁知道什么不清楚 |
| `设定/常识约束.md` | 工资、房租、技术能力、法律流程等现实常识漂移 |

## 真相文件

`设定/真相文件/` 是写作时的结构化事实源。Markdown 设定底座负责给人读，JSON 真相文件负责给流水线检查和编译章节约束。

| 文件 | 用途 |
|---|---|
| `characters.json` | 人物现实锚点、职业收入、居住逻辑、动机、声纹、行为边界 |
| `locations.json` | 地点成本、通勤、权限、消费水平、场景用途 |
| `factions.json` | 势力资源、限制、利益关系、行动边界 |
| `events.json` | 事件因果、证据链、影响范围、剧情债 |
| `relationships.json` | 信任等级、冲突、信息差、关系变化规则 |
| `resources.json` | 金钱、技能、权限、道具、系统能力及使用代价 |
| `foreshadowing.json` | 伏笔埋设、回收计划、遗忘风险 |

## 未知事实（open_questions）

每个真相文件都支持 `open_questions`，用于显式登记尚未确定的事实：

```json
"open_questions": [
  {"entity_id": "char_001", "field": "motivation", "reason": "作者尚未确定", "critical": true, "chapters": [12]}
]
```

- `critical: true`（默认）→ 编译进 `rule_stack.unknown_facts` 和 `blockers`，`pre_write_check` 阻断。
- `critical: false` → 只警告，不阻断。
- `chapters` 可选；不填则对所有章节生效。
- 记录的 `status` 为 `unknown` 或 `待定` 时，也会被收集为未知事实。

`rule_stack.write_ready=false` 表示存在 critical 未知事实；此时禁止起草。

`rule_stack` 还包含 `assumed_facts` 和 `evidence_policy`：

- `active_rules[].evidence_level`：`confirmed`（真相文件 / 细纲 / 上一章）/ `inferred`（题材惯例 / 风格 DNA）/ `assumed`（模型猜测）。
- `assumed_facts`：critical 的假设事实；非空时 `write_ready=false`，`pre_write_check` 与 `writing_gate` 都会阻断。
- 正文只能使用 `confirmed`；`inferred` 必须标明依据；`assumed` 禁止进入正文。

## 作者真相 / 读者已知

`events.json` 的记录支持：

```json
"reader_known": false,
"reveal_status": "未揭示",
"reveal_chapter": 20
```

`foreshadowing.json` 的 `reader_known` 表示钩子是否已被读者看到；`payoff_plan` 始终属于作者真相。
`characters.json` 支持 `knowledge_boundary`（角色明确知道）和 `secrets`（作者独有、角色不知道）。

`compile` 会生成 `rule_stack.truth_layers`（`author_truth` / `reader_known` / `unrevealed_facts` / `character_knowledge`），并写出派生视图：

```text
追踪/时间线/作者真相.md
追踪/时间线/读者已知.md
```

这些视图自动生成，禁止手改；源数据仍是 `设定/真相文件/`。写入护栏会拦截对 `追踪/时间线/*`、`追踪/上下文.md`、`追踪/伏笔.md`、`追踪/角色状态/*`、`追踪/情绪账.md`、`追踪/战力阶梯.md` 的直接编辑；确需修复时设置 `NOVEL_ALLOW_STATE_WRITE=1`。

情绪账与战力阶梯也是派生视图：

```text
追踪/情绪账.md        # 温度档、爽点类型、憋屈累计、上次释放
追踪/战力阶梯.md      # 角色层级、能力、代价、获得章、打不过谁
摘要/emotion_ledger.json
```

`project_bootstrap_pipeline.py init` 会创建模板；`seal` 会校验 7 个 JSON 全部补齐且无占位词。每章 `write_pipeline.py pre` 会生成：

```text
摘要/chapter_NNN_knowledge_pack.json
摘要/chapter_NNN_rule_stack.json
素材/chapter_NNN_truth_brief.md
摘要/chapter_NNN_truth_delta.json
```

`knowledge_pack.json` 是指针清单，不缓存全文：`required` 为每章必读项，`selected_routes` 为章节号/标题/细纲场景命中的路由，`missing_required` / `missing_selected` 记录缺失文件，`status` 为 `ok|warning`，`retrieval` 为按 `20_Characters` / `30_Plot` / `40_Writing` 过滤后的检索摘要。检索结果按 `stage=route`（选中路由目录）优先，`stage=fallback`（其余技法目录）补位；已列入 `selected_routes` 的文件不会重复出现在 `retrieval`。

写作阶段还会生成：

```text
摘要/chapter_NNN_taskbook.md        # context-agent 五段写作任务书
摘要/chapter_NNN_review.json        # reviewer 结构化审稿契约
素材/审稿报告_chNNN.md              # 由 review.json 渲染的人读报告
```

`chapter_NNN_review.json` 的 schema 见 [`../references/review-result-schema.md`](../references/review-result-schema.md)。只要该文件存在，`blocking_count > 0`、契约无效或 `stale` 都会阻断 quality 与 commit；`tribunal` 模式下文件缺失也会阻断。审稿通过 `target`、`basis` 和 `expected_versions` 绑定正文与审稿输入；正文、rule_stack、taskbook、memory_pack 或流程版本变更后旧审稿自动变为 `stale`。revision 记录位于 `素材/revisions/chapter_NNN/current.json` 和 `history/`。blocker/major 必须带 `source_refs` 原文引用。

每章 `post` 会强制校验 `chapter_NNN_truth_delta.json`。正文新增的人物状态、地点事实、势力行动、事件影响、关系变化、资源变化、伏笔变化，都必须写入 delta；否则 post 不通过。

`post` 会自动生成：

```text
素材/truth_delta_candidates_chNNN.json
素材/truth_delta_candidates_chNNN.md
```

候选报告会回写到 `chapter_NNN_truth_delta.json` 的 `auto_extraction`。只要 `review_status=needs_review`，delta 校验就不通过；必须审查候选事实，把属实项写入 observations/updates，把误报写进 review_note，最后改为 `reviewed`。

短篇/自由创作：

```text
novel_output/{平台}/{小说名}/
├── 正文/
├── 摘要/
├── 记忆/
├── 素材/
├── outline.md
└── novel_state.json
```

全局查询读模型：

```text
novel_output/_workspace/index/story_index.sqlite3
```

该 SQLite 文件由 `tools/sync_story_index.py` 自动生成，可删除后重建；它不存放正文或唯一事实，不纳入章节正文目录，也不替代项目源文件。

知识库检索读模型：

```text
novel_output/_workspace/index/knowledge_index.sqlite3
```

该文件由 `tools/knowledge_search.py` 自动生成，保存文档路径、词项和检索所需正文副本；支持词法和 TF-IDF 稀疏向量检索。删除后可从 `knowledge_base/` 重建，不替代知识库源文件。

历史张力趋势报告位于 `素材/tension/chapter_NNN_tension.json`。`source=heuristic` 的报告是可回溯估算，只供 Dashboard 趋势展示；启用张力契约时，仍必须提供正式章节曲线并通过契约校验。

`素材/revisions/` 下的 `snapshots/` 用于恢复，`proposals/` 用于人工审核前的 diff；proposal 的基线正文发生变化后必须重新生成，不能强制覆盖。

## Chapter Passport

每章完成后生成：

```text
摘要/chapter_NNN_passport.json
```

推荐字段：

```json
{
  "chapter": 12,
  "title": "章节标题",
  "chapter_file": "正文/第012章_章节标题.md",
  "word_count": 0,
  "pipeline_result": "pending|pass|fail",
  "pipeline": {
    "knowledge_pack": "pass|warning|fail|skipped",
    "truth_compile": "pass|fail|skipped",
    "truth_delta_template": "pass|fail|skipped",
    "pre_write_check": "pass|fail|skipped",
    "writing_gate": "pass|fail|skipped",
    "platform_preflight": "pass|fail|skipped",
    "post_write_audit": "pass|fail|skipped",
    "opening_score": "pass|warning|skipped",
    "normalizer": "pass|fail|skipped",
    "truth_delta_extract": "pass|fail|pending",
    "truth_delta": "pass|fail|pending",
    "truth_sync": "pass|fail|pending",
    "style_calibration": "pass|warning|fail|skipped",
    "character_consistency": "pass|warning|fail|skipped",
    "quality_review": "pass|pending|skipped",
    "review_result": "pass|fail|missing",
    "tension_curve": "pass|fail|skipped",
    "contract_validation": "pass|fail|skipped",
    "memory_sync": "pass|fail|pending",
    "emotion_ledger": "pass|fail|skipped"
  },
  "inputs": {
    "knowledge_pack": "",
    "taskbook": "",
    "review_result": "",
    "memory_pack": "",
    "rule_stack": "",
    "truth_brief": "",
    "truth_delta": "",
    "truth_delta_candidates": "",
    "truth_delta_candidates_review": "",
    "truth_delta_report": "",
    "normalizer_report": "",
    "opening_score_report": "",
    "emotion_ledger": "",
    "normalizer_task": "",
    "tension_report": "",
    "contract_report": ""
  },
  "workflow": {
    "schema_version": "1.0",
    "stage": "pre|draft|audit|truth|quality|memory|commit",
    "status": "pending|running|pass|blocked",
    "last_completed_stage": "",
    "next_action": "",
    "attempts": {},
    "error": "",
    "updated_at": ""
  },
  "scene_index": {
    "enabled": false,
    "count": 0,
    "passed": 0,
    "blocked": 0,
    "next_scene": 0,
    "status": "disabled",
    "path": ""
  },
  "quality_mode": "deterministic|balanced|tribunal",
  "changes": {
    "character_state_changes": [],
    "new_foreshadowing": [],
    "resolved_foreshadowing": [],
    "world_state_changes": []
  },
  "publish": {
    "platform": "",
    "status": "not_synced|draft|published",
    "synced_at": ""
  },
  "updated_at": ""
}
```

## novel_state.json 必备区块

```json
{
  "title": "",
  "platform": "",
  "current_chapter": 0,
  "word_count": 0,
  "revision_history": [],
  "audit_history": [],
  "strand_tracking": {
    "chapters": []
  },
  "publish_state": {}
}
```

立项通过后还必须包含：

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

## 写入规则

- `正文/` 只允许章节正文；审稿报告、项目元数据和扫描结果写入 `素材/reports/`，`project_bootstrap.json` 写入 `记忆/`。
- `novel_state.json` 的历史备份写入 `素材/state_backups/`，不散落在项目根目录。
- 平台字数与内容模式默认值统一读取 `knowledge_base/60_Platform/_PROFILES.json`；每章平台预检写入 `素材/platform_preflight_chNNN.json`。
- `素材/runs/chapter_NNN.lock` 是临时并发锁，正常流程结束后必须自动消失；残留锁需要确认无运行进程后再清理。
- 正文变更后必须更新 passport。
- 润色、审稿、重写必须写入 `revision_history`。
- 发布同步必须写入 `publish.status`。
- 角色状态、伏笔状态变化必须同步到 `knowledge_base/80_Projects/{小说名}/` 或 `记忆/`。

## 单一写者与一致性契约

- 状态文件（`novel_state.json`、`摘要/chapter_NNN_passport.json`、`素材/commits/chapter_NNN.commit.json`、`设定/真相文件/*.json`）只能由 `write_pipeline.py` / `project_bootstrap_pipeline.py` / `story_truth_manager.py` 写入；skill、子代理和域包只能读。
- commit 必须绑定 `chapter`、`passport`、`audit`、`truth_delta` 四类产物；缺一即 `verify_project_integrity.py` 报 ERROR。
- review 的 `target.sha256` 必须与正文一致；`stale` / `blocked` / `invalid` 不得伴随 accepted commit。
- `rule_stack.write_ready=false`、存在 critical `unknown_facts` 或存在 critical `assumed_facts` 时，正文文件不得存在。
- 交叉校验命令：`python3 tools/verify_project_integrity.py --novel-dir "{小说目录}" --json --strict`。
