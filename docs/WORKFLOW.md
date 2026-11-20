# Workflow

> 本文件描述插件的项目级工作流：调研 → 创意 → 立项 → 写章 → 发布。
>
> 章节内部的强状态机仍以 [`novel_creation_promax/references/orchestrator.md`](../novel_creation_promax/references/orchestrator.md) 和 [`PIPELINE.md`](../novel_creation_promax/docs/PIPELINE.md) 为准。

## 总览

```text
research ──→ idea ──→ init ──→ write ──→ publish
  │            │         │         │          │
调研报告      创意卡      seal      首章 commit  发布记录
```

| 阶段 | 命令 | 必须产物 | 门禁 |
|---|---|---|---|
| `research` | `/novel-creator-pro:research` | `素材/调研/*.md` | 报告存在且非空 |
| `idea` | `/novel-creator-pro:idea` | `创意/创意卡_*.md` | 调研报告存在 |
| `init` | `/novel-creator-pro:init` | 立项资料 + `seal` | 创意卡存在且 `can_write_chapter=true` |
| `write` | `/novel-creator-pro:write` | `素材/commits/chapter_*.commit.json` | 至少一个 accepted commit |
| `publish` | `/novel-creator-pro:publish` | `novel_state.publish_state` | 至少一个已同步/已发布状态 |

## 状态文件

工作区级状态：

```text
${CLAUDE_PROJECT_DIR}/novel_output/_workspace/workflow.json
```

示例：

```json
{
  "schema_version": "1.0",
  "stage": "idea",
  "status": "done",
  "platform": "番茄",
  "genre": "都市",
  "research_report": "素材/调研/2026-11-20_番茄_都市_热门方向.md",
  "idea_card": "",
  "novel_dir": "",
  "history": [],
  "overrides": [],
  "created_at": "2026-11-20T...",
  "updated_at": "2026-11-20T..."
}
```

- `stage` 是**最后完成的阶段**；启动后为空，完成调研后变为 `research`，以此类推。
- `next` 由工具计算。
- `history` 记录每次推进；`overrides` 记录强制跳阶段及原因。
- 状态只写工作区，不写插件目录。

推进示例：

```text
start                → stage: ""
advance --to research → stage: "research"
advance --to idea     → stage: "idea"
advance --to init     → stage: "init"
advance --to write    → stage: "write"
advance --to publish  → stage: "publish"
```

## 命令

```bash
# 启动
python3 "${CLAUDE_PLUGIN_ROOT}/tools/workflow.py" --workspace "${CLAUDE_PROJECT_DIR}" \
  start --platform 番茄 --genre 都市

# 查看
python3 "${CLAUDE_PLUGIN_ROOT}/tools/workflow.py" --workspace "${CLAUDE_PROJECT_DIR}" status
python3 "${CLAUDE_PLUGIN_ROOT}/tools/workflow.py" --workspace "${CLAUDE_PROJECT_DIR}" status --json

# 只校验，不改状态
python3 "${CLAUDE_PLUGIN_ROOT}/tools/workflow.py" --workspace "${CLAUDE_PROJECT_DIR}" \
  gate --to init --novel-dir "novel_output/番茄/书名"

# 推进
python3 "${CLAUDE_PLUGIN_ROOT}/tools/workflow.py" --workspace "${CLAUDE_PROJECT_DIR}" \
  advance --to idea

python3 "${CLAUDE_PLUGIN_ROOT}/tools/workflow.py" --workspace "${CLAUDE_PROJECT_DIR}" \
  advance --to init --novel-dir "novel_output/番茄/书名"

python3 "${CLAUDE_PLUGIN_ROOT}/tools/workflow.py" --workspace "${CLAUDE_PROJECT_DIR}" \
  advance --to write --novel-dir "novel_output/番茄/书名"

python3 "${CLAUDE_PLUGIN_ROOT}/tools/workflow.py" --workspace "${CLAUDE_PROJECT_DIR}" \
  advance --to publish --novel-dir "novel_output/番茄/书名"
```

## 与现有门禁的关系

| 门禁 | 负责 | 不可替代 |
|---|---|---|
| `workflow.py` | 项目级阶段顺序与跨阶段证据 | 不能替代 `seal`、`writing_gate`、`post_write_audit` |
| `project_bootstrap_pipeline.py seal` | 立项资料完整性 | `workflow.py` 的 `init` 门禁会检查 `can_write_chapter` |
| `write_pipeline.py` | 单章阶段与断点续跑 | 每章仍必须走 pre/post |
| `writing_gate.py` | Pass 1 质量门禁 | 不影响工作流阶段 |
| `verify_project_integrity.py` | 章节/passport/commit/state 一致性 | 不判断项目阶段 |

工作流是“外层导航”，不是第二套章节状态机。任何阶段门禁失败，先修证据，不要改状态文件绕过。

## 跳过阶段

默认禁止跳阶段。确实需要时：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/workflow.py" --workspace "${CLAUDE_PROJECT_DIR}" \
  advance --to write --novel-dir "novel_output/番茄/书名" \
  --force --reason "已有存稿，补走流程"
```

- 必须提供 `--reason`；
- 写入 `overrides`，不会静默跳过；
- 不能替代章节 commit 或发布记录。

## 失败处理

| 失败 | 处理 |
|---|---|
| 缺调研报告 | 先跑 `/research`，或 `--force --reason` 记录跳过 |
| 缺创意卡 | 先跑 `/idea` |
| `seal` 未通过 | 补齐立项资料后重跑 `seal` |
| 没有 accepted commit | 走完 `write_pipeline.py post` |
| 没有发布记录 | 确认平台同步/发布完成 |

`workflow.py status --json` 会返回 `missing` 列表，可直接用于 Dashboard 或 CI。
