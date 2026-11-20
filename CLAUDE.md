# CLAUDE.md

> 本文件是 Claude Code 在**插件源码仓库**中的入口。
> 完整开发规则、目录结构和行为红线以 [AGENTS.md](AGENTS.md) 为准；本文件只放最短的执行约束，避免两份规则漂移。

## 先读

1. [AGENTS.md](AGENTS.md) — 行为规则、目录结构、质量红线
2. [docs/COMMANDS.md](docs/COMMANDS.md) — 命令、脚本职责、依赖
3. [novel_creation_promax/docs/PIPELINE.md](novel_creation_promax/docs/PIPELINE.md) — 写章流水线与门禁
4. [docs/WORKFLOW.md](docs/WORKFLOW.md) — 外层工作流与看板

## 硬约束

- **这是插件源码仓库，不是写作工作区**。用户作品在独立工作区（当前为 `~/Desktop/Narain_projects/novel-workspace/`）。
- **插件根只读**：技能、脚本、知识库、参考都在这里；运行产物写 `${CLAUDE_PROJECT_DIR}`。
- **改动优先落 `novel_creation_promax/`**；`skills/` 是插件发现层，详细规则只维护在核心层。
- **不要编辑退役版本**：`novel_creation_max/`、`novel_creation_max2.0/`、`skill_super-novel-writer/`。
- **状态文件单一写者**：`novel_state.json`、passport、commit、真相文件只能由流水线脚本写入，禁止手改。
- **提交前跑** `bash tools/ci.sh`；不要只跑部分测试。
- **新增/修改技能**后同步 `skill_health_check.py`、`MODE_REGISTRY.md` 和对应测试。

## 两个 CLAUDE.md 的分工

| 文件 | 作用 |
|---|---|
| 本文件 / `AGENTS.md` | 开发这个插件时的规则 |
| `novel-workspace/CLAUDE.md` | 写小说时的项目说明（进度、目录、常用命令） |

安装给第三方用户时，插件根 `CLAUDE.md` 不会成为用户项目的指令；用户侧的规则由 `skills/novel-creator/SKILL.md`、`hooks/session_start.py` 和工作区自己的 `CLAUDE.md` 提供。
