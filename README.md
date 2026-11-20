# novel-creator-pro

中文网文创作、审计、记忆与多平台发布的 Claude Code 插件。

它把「立项 → 大纲/细纲 → 写章 → 审计 → 记忆回填 → 发布」串成一条带门禁的流水线，核心目标是长篇连载不崩设定、不丢伏笔、不漂风格。

## 安装

在包含本仓库的目录执行：

```bash
claude plugin marketplace add ./
claude plugin install novel-creator-pro@novel-creator-pro-market --scope user
```

从远端 marketplace 安装：

```bash
claude plugin marketplace add penghang1223/novel-creator-promax
claude plugin install novel-creator-pro@novel-creator-pro-market --scope user
```

> 仓库已公开，可直接安装。

安装后可用：

```text
/novel-creator-pro:research  平台热门方向调研
/novel-creator-pro:idea      创意生成 + 五维评分
/novel-creator-pro:workflow  查看工作流阶段与下一步
/novel-creator-pro:init      立项
/novel-creator-pro:write     写章
/novel-creator-pro:review    审稿
/novel-creator-pro:doctor    体检
```

典型流程：

```text
调研 → 创意 → 立项 seal → 大纲/细纲 → 写章 → 审稿 → 发布
```

阶段状态与门禁见 [`docs/WORKFLOW.md`](docs/WORKFLOW.md)。

## 环境要求

- Python 3.9+（建议 3.10+）
- 核心流水线只依赖标准库
- 可选依赖：Pillow（封面）、jieba（风格 DNA/人物一致性）、requests（知识摄入）、FastAPI（Dashboard）、Playwright（自动发布）

运行体检：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/plugin_doctor.py" --root "${CLAUDE_PROJECT_DIR}"
```

## 工作区约定

插件资产只读，用户数据全部写在当前项目：

```text
${CLAUDE_PROJECT_DIR}/
├── novel_output/{平台}/{书名}/
│   ├── 正文/ 摘要/ 素材/ 设定/ 细纲/
│   └── novel_state.json
├── 素材/调研/                 # 平台热门方向报告（本次运行产物）
├── 创意/                      # 创意卡与五维评分（本次运行产物）
├── 创意库/                    # 长期创意库（创意卡/调研/_INDEX.md）
├── MEMORY.md
└── .claude/memory/
```

- 插件根（`${CLAUDE_PLUGIN_ROOT}`）**禁止写入**；更新后旧目录会被清理。
- 章节状态唯一真源：`摘要/chapter_NNN_passport.json` + `素材/commits/`。
- 跨产物一致性校验：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/verify_project_integrity.py" \
  --novel-dir "${CLAUDE_PROJECT_DIR}/novel_output/番茄/书名"
```

## 技能

| 技能 | 用途 |
|---|---|
| `novel-creator` | 总路由与全局契约 |
| `novel-market-research` | 平台热门方向、榜单题材、可执行选题 |
| `novel-idea` | 创意生成、创意卡、五维评分 |
| `novel-workflow` | 项目级阶段与下一步门禁 |
| `novel-project-planning` | 立项、设定、大纲、分卷、细纲 |
| `novel-chapter-write` | 写章、续写、润色 |
| `novel-memory` | 记忆初始化、唤醒、回填、体检 |
| `novel-review` | 单章精审、批量快审 |
| `novel-publish` | 平台格式转换、同步、发布 |
| `novel-knowledge-ingestion` | 教程/案例/链接知识摄入 |
| `novel-doctor` | 环境、依赖、工作区、产物一致性 |
| `novel-diagnose` | 上线后数据诊断、断流急救、切书决策 |

> `skills/` 是技能唯一根目录：每个技能一个目录，`SKILL.md`、`scripts/`、`references/`、`assets/` 都在其中。`novel_creation_promax/` 只保留核心库、流水线脚本和共享参考，不再放 `SKILL.md`。

## 辅助技能（随插件分发）

位于 `skills/`，与主技能一起安装。由主链技能按需调用，也可用自然语言直接触发：

| 技能 | 用途 |
|---|---|
| `name-generator` | 角色命名、撞名/AI 命名检查 |
| `chapter-hook` | 章首/章末钩子、微钩子、钩型轮换 |
| `title-blurb` | 书名、简介、标签、书测素材 |
| `deai-check` | AI 味诊断与五层改写 |
| `platform-format` | 平台稿格式、字数门禁、草稿同步 |
| `data-diagnosis` | 上线后 11 项数据诊断 |
| `idea-library` | 长期创意库：查重、归档、索引、搜索 |

## 子代理与结构化审稿

| 子代理 | 职责 | 权限 |
|---|---|---|
| `context-agent` | 把细纲、记忆、真相约束压缩成五段写作任务书 | 只读 |
| `reviewer` | 按五维标准审稿，只返回严格 JSON | 只读 |
| `data-agent` | 从正文提取 truth delta 草案 | 只读 |

审稿结论分两层：`摘要/chapter_NNN_review.json` 是机器契约，`blocking_count > 0` 会阻断 quality 与 commit；`素材/` 下的审稿报告由 JSON 渲染，只给人看。审稿通过 `target.sha256` 绑定正文版本，正文改动后旧审稿自动失效（`stale`）；blocker/major 必须带 `source_refs` 原文引用。

```bash
python3 tools/review_result.py save --novel-dir "{小说目录}" --chapter N --input /tmp/reviewer.json
python3 tools/review_result.py status --novel-dir "{小说目录}" --chapter N --json
python3 tools/review_result.py render --novel-dir "{小说目录}" --chapter N \
  --output "{小说目录}/素材/审稿报告_chNNN.md"
```

## 运行时护栏

- `SessionStart`：播报工作区、当前书籍/章节、Python 与可选依赖状态。
- `PreToolUse`：拦截对插件资产的写入，以及对 passport、summary、commit、真相文件、`novel_state.json` 和派生追踪视图的直接写入。
- `PreToolUse`：首次创建 `正文/第N章...` 时，`细纲/` 必须有对应章节；缺失则阻断。
- 流水线运行时可设置 `NOVEL_PIPELINE_ACTIVE=1` 放行；人工修复可设置 `NOVEL_ALLOW_STATE_WRITE=1`。

## 开发

```bash
python3 -m unittest discover -s tests
claude plugin validate ./
bash tools/ci.sh          # 测试 + 行为评测 + 技能健康检查 + 插件体检
```

开发时建议用 `--plugin-dir` 原地加载，避免每次改动都重装：

```bash
claude --plugin-dir .
```

已安装的插件会复制到 `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`。
如果改完源码要验证安装版，执行：

```bash
claude plugin update novel-creator-pro@novel-creator-pro-market
```

源码结构：

```text
.claude-plugin/     插件与 marketplace 清单
skills/             插件技能（每个技能一个目录：SKILL.md + scripts/references/assets）
agents/             子代理（任务书 / 审稿 / 事实提取）
commands/           斜杠命令
hooks/              SessionStart 与写入护栏
novel_creation_promax/  核心库、流水线脚本、共享参考（无 SKILL.md）
knowledge_base/     裁剪后的只读知识库
tools/              运维与校验脚本
tests/              标准库回归测试
```

## 参考与致谢

部分质量门禁、开篇评分、数据诊断和台账设计参考了 novel-engine（MIT）、oh-story-claudecode（MIT）、webnovel-writer（GPL-3.0）和 AI_NovelGenerator（AGPL-3.0）的公开设计；代码按本项目结构重写，未直接复制实现。

## 许可

本项目使用 [GNU General Public License v3.0](LICENSE)（GPL-3.0-only）。

你可以自由使用、修改和分发本项目；分发衍生作品时必须同样以 GPL-3.0 授权，并提供对应源代码。

知识库中的平台规则、榜单趋势和调研内容仅作学习参考；第三方数据与文章版权归原作者，引用处保留来源。对外分发时请保留本说明。
