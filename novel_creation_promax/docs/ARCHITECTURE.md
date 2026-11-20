# Architecture

> 本文描述 `novel_creation_promax` 的系统边界、数据流和唯一真源。日常执行细节见 `references/orchestrator.md`，功能编号见 `MODE_REGISTRY.md`。

## 系统目标

小说创作 Pro Max 是面向中文网文的创作技能系统。它不是单个 prompt，而是由技能入口、知识库、记忆中台、审计脚本和发布辅助组成的闭环。

核心目标：

- 立项时避免创意、设定、大纲缺口。
- 连载时保持人物、伏笔、风格、节奏一致。
- 写后用脚本兜住字数、AI痕迹、重复、OOC 等硬问题。
- 将用户纠正沉淀到共享记忆和知识库，而不是停留在对话里。

## 组件边界

| 组件 | 责任 | 不负责 |
|---|---|---|
| 路由技能 `skills/novel-creator/SKILL.md` | 触发、导航、最小工作流说明 | 大量规则细节 |
| `MODE_REGISTRY.md` | 功能编号和模式唯一真源 | 具体写作技巧 |
| `references/orchestrator.md` | 阶段、门禁、调用顺序 | 知识库内容本身 |
| `references/trigger-rules.md` | 题材/技巧/审稿/连贯性触发 | 模式编号 |
| `references/knowledge-pack-workflow.md` | 每章知识包组装 | 长篇记忆 CRUD |
| `skills/novel-memory/` | 风格、人物、剧情、上下文、历史记忆 | 正文创作 |
| `skills/novel-review/` | LLM 深度审稿 | 硬性自动审计 |
| `scripts/` | 可执行门禁和确定性工具 | 创意判断 |
| `core/` | 路径、JSON、passport、章节/场景状态机、平台档案、故事索引、revision 控制、知识路由、项目注册表等共享确定性能力 | CLI 交互和业务流程编排 |
| `knowledge_base/` | 题材、技巧、质量、平台、项目知识 | 临时草稿缓存 |

## 数据流

```text
用户请求
  ↓
MODE_REGISTRY.md 选择模式
  ↓
路由技能导航到对应 reference / script
  ↓
知识库 + 记忆包 + 项目文件
  ↓
真相文件校验 + rule_stack 编译
  ↓
正文/大纲/审稿/润色产物
  ↓
脚本审计与 passport 记录
  ↓
novel_state.json + novel-memory + knowledge_base/80_Projects
```

## 正文写作闭环

```text
细纲 + 记忆包 + 知识包 + 真相文件
  ↓
story_truth_manager.py validate/compile
  ↓
pre_write_check.py
  ↓
Pass 1 剧情稿
  ↓
writing_gate.py
  ↓
Pass 2 去AI修订
  ↓
post_write_audit.py
  ↓
story_truth_manager.py normalize + validate-delta + apply-delta
  ↓
style_calibrator.py + character_consistency_checker.py
  ↓
chapter passport + chapter summary
  ↓
memory_manager.py sync-chapter
```

## 唯一真源

| 主题 | 唯一真源 |
|---|---|
| 功能编号 | `MODE_REGISTRY.md` |
| 执行阶段 | `references/orchestrator.md` |
| 触发规则 | `references/trigger-rules.md` |
| 知识包 | `references/knowledge-pack-workflow.md` |
| 机器可读知识路由 | `knowledge_base/_ROUTES.json` |
| 项目注册表 | `knowledge_base/80_Projects/_PROJECT_REGISTRY.json`（由 `tools/build_project_registry.py` 生成） |
| 历史项目别名 | `knowledge_base/80_Projects/_PROJECT_ALIASES.json`（显式记录编号漂移与知识库孤儿项目） |
| 结构化事实源 | `设定/真相文件/*.json` |
| 输出结构 | `docs/ARTIFACTS.md` |
| 数据访问层级 | `docs/DATA_ACCESS_LEVELS.md` |
| 章节流水线状态 | `摘要/chapter_NNN_passport.json` |
| 项目状态 | `novel_state.json`，逐步迁移至 `core/project_state.py` 定义的 v2 结构 |
| 长篇记忆 | `skills/novel-memory/` |
| 查询读模型 | `novel_output/_workspace/index/story_index.sqlite3`，由源文件重建，不是事实真源 |
| 知识检索读模型 | `novel_output/_workspace/index/knowledge_index.sqlite3`，由 `knowledge_base/` 重建，不保存唯一事实 |
| 用户偏好/纠正 | `.claude/memory/` |

## 维护原则

- 新功能先登记到 `MODE_REGISTRY.md`，再写入 `skills/novel-creator/SKILL.md`。
- 新脚本必须能从项目根目录执行。
- 新质量规则优先进入脚本或知识库，不直接堆到路由技能。
- CLI、Dashboard、发布脚本共享路径/章节/passport 逻辑时，优先调用 `novel_creation_promax/core/`，不要复制正则。
- 用户可控的平台名和小说目录必须通过 `core.paths.get_novel_dir` 解析，禁止直接拼接路径。
- 每章状态以 chapter passport 为准；summary 和 novel_state 只做摘要索引或兼容读取。
- `passport.workflow` 是章节阶段状态源；`novel_state.resume_point` 只保存跨进程续跑提示，不能替代 passport。
- `write_pipeline.py post` 通过 `--phase` 暴露阶段边界；阶段产物和状态必须在每个边界持久化。
- 平台默认值集中在 `knowledge_base/60_Platform/_PROFILES.json`，门禁脚本不得重复维护平台常量。
- SQLite 故事索引只服务 Dashboard、质量报告和聚合查询；正文、真相文件、passport、summary、commit 文件始终是唯一真源。
- 任何索引字段都必须可以从源文件重建；源文件删除后，索引同步必须删除对应记录，禁止保留幽灵章节。
- 自动修改必须先进入 `素材/revisions/` 的 snapshot/proposal；批准时校验基线 hash，过期 proposal 不能覆盖人工新稿。
- 场景 passport 只作为显式启用章节的细粒度门禁，不改变历史章节的兼容行为。
- Dashboard 直接编辑正文后必须让当前章节 passport 失效，并把断点指向 `post`，不能保留旧的通过状态。
- `novel_state.json` 的批量迁移默认 dry-run，只有显式 `tools/normalize_project_state.py --apply` 才写回，并保留备份。
- `memory` 与 `记忆` 只能有一个主目录；使用 `tools/merge_memory_aliases.py` 无损收敛，冲突必须人工决策。
- 新项目由 `project_bootstrap_pipeline.py` 生成 `项目章程.md` 和 `风险登记表.md`；项目知识库的 `变更记录.md` 记录跨章节设定变更。
- 项目目录编号发生历史漂移时，先写入 `_PROJECT_ALIASES.json` 并保留原目录；只有业务确认后才允许重命名目录。
- 注册表以 `novel_output` 的当前编号为运行时 canonical id，历史知识库编号写入 `legacy_project_ids`，避免静默覆盖或误合并项目。
- 修改知识路由时先改 `knowledge_base/_ROUTES.json`，再同步人读版 `_ROUTING.md`。
- 任何章节推进、角色状态变化、伏笔变化，必须同步项目级知识库或记忆系统。
章节质量层现在额外提供三类可选增强：知识库词法/TF-IDF 检索、章节张力曲线契约、JSON 结构契约校验。它们都通过报告文件留痕，并且只有项目显式启用张力契约时才成为强制门禁。
