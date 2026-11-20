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

```text
/plugin install novel-creator-pro --marketplace <owner>/<repo>
```

安装后可用：

```text
/novel-creator-pro:research  平台热门方向调研
/novel-creator-pro:idea      创意生成 + 五维评分
/novel-creator-pro:init      立项
/novel-creator-pro:write     写章
/novel-creator-pro:review    审稿
/novel-creator-pro:doctor    体检
```

典型流程：

```text
调研 → 创意 → 立项 seal → 大纲/细纲 → 写章 → 审稿 → 发布
```

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
├── 素材/调研/                 # 平台热门方向报告
├── 创意/                      # 创意卡与五维评分
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
| `novel-project-planning` | 立项、设定、大纲、分卷、细纲 |
| `novel-chapter-write` | 写章、续写、润色 |
| `novel-memory` | 记忆初始化、唤醒、回填、体检 |
| `novel-review` | 单章精审、批量快审 |
| `novel-publish` | 平台格式转换、同步、发布 |
| `novel-knowledge-ingestion` | 教程/案例/链接知识摄入 |
| `novel-doctor` | 环境、依赖、工作区、产物一致性 |

## 运行时护栏

- `SessionStart`：播报工作区、当前书籍/章节、Python 与可选依赖状态。
- `PreToolUse`：拦截对插件资产的写入，以及对 passport、summary、commit、真相文件、`novel_state.json` 的直接写入。
- 流水线运行时可设置 `NOVEL_PIPELINE_ACTIVE=1` 放行；人工修复可设置 `NOVEL_ALLOW_STATE_WRITE=1`。

## 开发

```bash
python3 -m unittest discover -s tests
claude plugin validate ./
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
skills/             插件技能适配层
commands/           斜杠命令
hooks/              SessionStart 与写入护栏
novel_creation_promax/  核心技能、脚本、参考
knowledge_base/     裁剪后的只读知识库
tools/              运维与校验脚本
tests/              标准库回归测试
```

## 许可

当前为私有项目（`UNLICENSED`）。对外发布前请补充明确的 LICENSE。
