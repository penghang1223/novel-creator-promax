# 审稿结果契约（Chapter Review Result）

> 本文件是 `摘要/chapter_NNN_review.json` 的唯一 schema 说明。reviewer 只返回 JSON，主流程用 `tools/review_result.py` 绑定正文、校验原文引用并落盘。

## 为什么需要它

审稿报告如果只是 Markdown，门禁无法判断"这章能不能提交"，也无法判断"这份审稿是不是针对当前正文"。把审稿结论拆成两层：

1. **机器层**：`摘要/chapter_NNN_review.json`，固定字段，`blocking_count` 可直接阻断 commit，`target.sha256` 绑定正文版本。
2. **人读层**：`素材/审稿报告_chNNN.md`，由 JSON 渲染，不参与门禁。

reviewer 只生产第 1 层；第 2 层由 `tools/review_result.py render` 生成。

## 文件位置

```text
{小说目录}/
├── 摘要/chapter_NNN_review.json      # 机器契约
└── 素材/审稿报告_chNNN.md            # 人读报告（由 render 生成）
```

## Schema

```json
{
  "schema_version": "1.0",
  "chapter": 12,
  "mode": "single",
  "target": {
    "chapter_file": "正文/第012章-标题.md",
    "sha256": "64 位十六进制 SHA-256",
    "word_count": 2980,
    "revision_id": "rev_20261120T130000_ab12cd34",
    "revision_version": 3
  },
  "basis": {
    "workflow": "novel-creator:chapter-write",
    "step": "review",
    "schema_id": "chapter_review",
    "schema_version": 1,
    "prompt_version": 1,
    "input_fingerprint": "64 位十六进制 SHA-256",
    "source_refs": [
      {"resource_type": "chapter", "id": "012", "sha256": "..."},
      {"resource_type": "rule_stack", "id": "012", "sha256": "..."},
      {"resource_type": "truth_brief", "id": "012", "sha256": "..."},
      {"resource_type": "taskbook", "id": "012", "sha256": "..."},
      {"resource_type": "memory_pack", "id": "012", "sha256": "..."}
    ]
  },
  "expected_versions": {
    "chapter:012": "...",
    "rule_stack:012": "...",
    "truth_brief:012": "...",
    "taskbook:012": "...",
    "memory_pack:012": "..."
  },
  "dimensions": {
    "dialogue":      {"score": 8, "summary": "对话有攻防，两处信息说得太直。", "issues": []},
    "coolpoint":     {"score": 7, "summary": "爽点有铺垫，反应层偏薄。", "issues": []},
    "structure":     {"score": 8, "summary": "冲突建立快，断章有效。", "issues": []},
    "anti_ai":       {"score": 6, "summary": "三处情绪标签。", "issues": []},
    "reading_power": {"score": 9, "summary": "章末信息差留得住人。", "issues": []}
  },
  "issues": [
    {
      "id": "R-001",
      "severity": "major",
      "assessment": "issue",
      "dimension": "anti_ai",
      "location": "第 3 段",
      "evidence": "他感到一阵难以言喻的愤怒。",
      "impact": "情绪标签化，读者无法通过行为感知人物状态。",
      "repair": "改成手部动作或对话停顿。",
      "source_refs": [
        {
          "quote": "他感到一阵难以言喻的愤怒。",
          "start": 128,
          "end": 140,
          "start_line": 12,
          "end_line": 12
        }
      ]
    }
  ],
  "blocking_count": 0,
  "status": "pass",
  "grade": "B",
  "summary": "整体可交付。",
  "generated_at": "2026-11-20T12:00:00"
}
```

## 字段规则

| 字段 | 类型 | 规则 |
|---|---|---|
| `schema_version` | string | 固定 `1.0` |
| `chapter` | int | 必须与文件名章号一致 |
| `mode` | string | `single` 或 `batch` |
| `target` | object | 必须是当前正文的精确版本；由 `target` 命令生成 |
| `target.sha256` | string | 64 位十六进制；正文变更后审稿自动变为 `stale` |
| `target.chapter_file` | string | 项目内相对路径，不允许 `..` 或绝对路径 |
| `target.revision_id` | string | 当前正文的不可变 revision；由 `target --ensure-revision` 生成 |
| `target.revision_version` | int | 与 `revision_id` 同时出现，从 1 递增 |
| `basis` | object | 审稿依据；由 `target --with-basis` 生成 |
| `basis.input_fingerprint` | string | 64 位 SHA-256；汇总全部依据资源 |
| `basis.source_refs` | array | 审稿实际读取的 chapter / rule_stack / truth_brief / taskbook / memory_pack |
| `expected_versions` | object | 资源键 → 审稿时的 SHA-256；任一变化则审稿 `stale` |
| `dimensions` | object | 必须包含五个键：`dialogue`、`coolpoint`、`structure`、`anti_ai`、`reading_power` |
| `dimensions.*.score` | int \| null | 0-10；无法判断时用 `null`，不要用 0 代替 |
| `dimensions.*.summary` | string | 非空；一句话说明该维度结论 |
| `issues` | array | 问题清单，可为空 |
| `issues[].id` | string | 章内唯一，如 `R-001` |
| `issues[].severity` | string | `blocker` / `major` / `minor` |
| `issues[].code` | string | 可选稳定错误码，如 `POV_LEAK`、`TIMELINE_BREAK`、`OOC`、`PLACEHOLDER` |
| `issues[].assessment` | string | `issue` / `resolved` / `unavailable` / `observation` |
| `issues[].dimension` | string | 五维之一，或 `cross` |
| `issues[].evidence` | string | 必填；人类可读的证据摘要 |
| `issues[].repair` | string | blocker 必填；必须可执行 |
| `issues[].source_refs` | array | blocker / major 必填；每条 `quote` 必须逐字来自正文 |
| `source_refs[].start` / `end` | int | 可选字符偏移（0-based，Unicode 码点）；提供时按原文切片精确匹配 |
| `source_refs[].start_line` / `end_line` | int | 可选行号（1-based）；无字符偏移时按行范围匹配 |
| `blocking_count` | int | 必须等于 `severity=blocker` 的问题数 |
| `status` | string | `pass` 或 `blocked`，由 `blocking_count` 推导 |
| `grade` | string | `S/A/B/C/D`；留空时按五维均分推导 |
| `summary` | string | 总评，一段话 |

## 角色知识边界（POV_LEAK）

审稿读取 `rule_stack.truth_layers`：

- `reader_known`：读者已经知道的事实
- `unrevealed_facts`：作者知道但尚未揭示的事实
- `character_knowledge`：每个角色明确知道的内容与作者独有秘密

如果正文让角色说出或利用了 `unrevealed_facts`，或超出 `character_knowledge.knows`，必须报告：

```json
{
  "id": "R-010",
  "severity": "blocker",
  "assessment": "issue",
  "code": "POV_LEAK",
  "dimension": "cross",
  "location": "第 6 段",
  "evidence": "角色说出了只有作者知道的真凶身份。",
  "impact": "读者尚未获得该信息，角色不可能知道。",
  "repair": "改成怀疑或错误推断，等揭示章再让角色确认。",
  "source_refs": [{"quote": "...原文...", "start": 0, "end": 10}]
}
```

## 严重度与 assessment

| severity | 含义 | 门禁行为 |
|---|---|---|
| `blocker` | 设定硬冲突、时间线断裂、上一章钩子未回应、严重 OOC、章末无钩子、正文占位符 | 阻断 quality 与 commit |
| `major` | 对话干涩、爽点缺反应层、场景硬切、明显 AI 味 | 不阻断，进入修复计划 |
| `minor` | 个别用词、局部节奏、可加强的描写 | 记录即可 |

`assessment` 用来区分问题状态：

| assessment | 含义 | source_refs |
|---|---|---|
| `issue` | 确认存在的问题 | blocker / major 必填 |
| `resolved` | 已在本轮修复 | 可选 |
| `unavailable` | 无法验证或审稿未完成 | 可省略 |
| `observation` | 记录性观察，不是缺陷 | 可选 |

## 审稿目标绑定

审稿绑定两层身份：

1. **内容身份**：`target.sha256` 是审稿时正文文件的 SHA-256。
2. **版本身份**：`target.revision_id` 是这次内容对应的不可变 revision。

`target --ensure-revision` 会在正文变化时创建新 revision：

```text
{小说目录}/素材/revisions/chapter_NNN/
├── current.json          # 当前 revision 指针
└── history/
    └── rev_....json      # 不可变历史
```

门禁会同时检查：

- 当前正文哈希是否等于 `target.sha256`
- `current.json` 的 `revision_id` 是否等于 `target.revision_id`
- `current.json` 的 `content_hash` 是否等于 `target.sha256`

任一不一致 → `stale`，quality 与 commit 阻断，必须重新审稿。

如果没有 `revision_id`，门禁仍按文件哈希判定，但会给出"未绑定 revision"警告。正常流程应使用 `target --ensure-revision`。

这样"审的是旧稿、提交的是新稿"不会静默通过；恢复旧 revision 或其它修改也不会误用旧审稿。

## 审稿依据（basis）

`target` 只绑定正文 revision；`basis` 绑定审稿实际读取的输入：

- `rule_stack`：本章编译后的真相约束
- `truth_brief`：本章真相摘要
- `taskbook`：context-agent 五段任务书
- `memory_pack`：本章记忆包
- 审稿流程版本：`workflow`、`step`、`schema_id`、`schema_version`、`prompt_version`

`expected_versions` 是这些资源的 SHA-256 快照。门禁会重新计算当前输入：

- 任一资源哈希变化 → `stale`
- 资源从缺失变为存在，或从存在变为缺失 → `stale`
- `input_fingerprint` 不一致 → `stale`

**不包含**原始真相文件和 passport：

- `post:truth` 会在审稿之后修改真相文件；把原始真相文件纳入 basis 会让本次审稿在自己的 post 流程中被判过期。
- passport 在每个 post 阶段都会更新，同理不适合作为审稿依据。

`rule_stack` 和 `truth_brief` 是真相文件的编译结果，已是 reviewer 的实际输入；设定变化后重新运行 `pre` 会更新它们，从而让旧审稿失效。

## 原文引用校验

`source_refs[].quote` 必须逐字出现在正文里。匹配优先级：

1. **字符偏移**：提供 `start` 时，必须满足 `正文[start:end] == quote`；未提供 `end` 时按 `start + len(quote)` 计算。
2. **行范围**：没有字符偏移但提供 `start_line` / `end_line` 时，quote 必须在该行范围内。
3. **全文包含**：两者都没有时，quote 只需逐字出现在正文中。

- quote 找不到或偏移不匹配 → 契约无效（`invalid`），commit 阻断
- blocker / major 没有 source_refs → 契约无效
- `assessment: "unavailable"` 的 blocker 可以没有 source_refs，但必须说明缺什么
- `end` 不能单独出现；`end < start` 视为无效

## JSON 语法防御

读取审稿 JSON 时会先检查重复字段。同一对象内出现重复 key（例如两个 `status`）会直接判为 `invalid`，不会让后一个值静默覆盖前一个。错误信息会给出 JSON 路径，例如 `$["issues"][0]["id"]`。

## 门禁语义

`core/review_result.py` 的 `review_gate()` 返回五种状态：

| status | 含义 | 处理 |
|---|---|---|
| `missing` | 没有审稿结果 | deterministic/balanced 可继续，tribunal 必须补 |
| `pass` | 契约有效、目标一致、无 blocker | 允许 commit |
| `blocked` | 契约有效、目标一致，但存在 blocker | 阻断 quality 与 commit |
| `invalid` | JSON 不符合契约，或引文未在正文中找到 | 阻断，必须先修 JSON |
| `stale` | 正文哈希、revision、rule_stack、taskbook、memory_pack 或流程版本与审稿记录不一致 | 阻断，必须重新审稿 |

一旦审稿文件存在，就必须被遵守；不存在不会被"假装通过"。

## 命令

```bash
# 取当前正文的审稿目标 + basis + expected_versions，必要时创建新 revision
python3 tools/review_result.py target --novel-dir "{小说目录}" --chapter 12 \
  --json --ensure-revision --with-basis

# 创建待填写模板（若正文存在会自动绑定 target）
python3 tools/review_result.py init --novel-dir "{小说目录}" --chapter 12

# 校验契约、目标哈希与原文引用
python3 tools/review_result.py validate --novel-dir "{小说目录}" --chapter 12

# 写入 reviewer JSON；正常流程应让 reviewer 自带 target
python3 tools/review_result.py save --novel-dir "{小说目录}" --chapter 12 --input /tmp/reviewer.json

# 兜底：reviewer 未计算哈希时，用当前正文和当前 revision 绑定 target
python3 tools/review_result.py save --novel-dir "{小说目录}" --chapter 12 \
  --input /tmp/reviewer.json --bind-target

# 查看门禁状态；--require 时缺失也算失败
python3 tools/review_result.py status --novel-dir "{小说目录}" --chapter 12 --require

# 渲染人读报告
python3 tools/review_result.py render --novel-dir "{小说目录}" --chapter 12 \
  --output "{小说目录}/素材/审稿报告_ch012.md"
```

## 与 quality_review 的关系

- `摘要/chapter_NNN_review.json`：五维质量审稿，绑定正文版本。
- `素材/quality_review_chNNN.json`：`tribunal` 模式要求的人工确认报告，字段和用途不同，继续保留。

两者同时存在时，`review.json` 的 blocker 或 stale 不受 `quality_review` 的 `status=pass` 影响；始终阻断。
