# AGENTS.md（插件源码仓库）

> **这是 `novel-creator-pro` 插件的源码仓库，不是用户写作工作区。**
>
> - 运行时行为规则在 [`skills/`](skills/) 和 [`novel_creation_promax/`](novel_creation_promax/)。
> - 用户作品、记忆和状态位于 `${CLAUDE_PROJECT_DIR}/novel_output/`，不在本仓库。
> - 插件根目录只读；任何运行期状态都写入工作区或 `${CLAUDE_PLUGIN_DATA}`。
> - 旧版项目说明保留在下方，作为开发和维护参考。

---

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **项目定位**：基于 Claude Code 的中文网文创作技能系统。核心由 markdown 技能定义 (`SKILL.md`) + Python 审计/记忆脚本 + Obsidian 知识库 + Playwright 浏览器自动发布组成。所有创作行为由 `novel_creation_promax/SKILL.md` 驱动。仓库提供 stdlib 回归测试、健康检查和 pre-commit hook，暂未接入远程 CI。
>
> **加载策略**：本文件只放**行为规则和红线**，常驻上下文。命令语法、工具清单、外部集成都移到 [`docs/`](docs/) 下按需读取，见文末「文档索引」。

## 双端共享记忆

本项目支持终端 Claude 和飞书 Claude 两个实例同时运行。**必须读取以下共享记忆文件**：

1. `MEMORY.md` — 共享记忆索引（启动时加载）
2. `.claude/memory/decisions/preferences.md` — 用户偏好与协作规则
3. `.claude/memory/active_novels/progress.md` — 当前小说进度
4. `.claude/memory/feedback/corrections.md` — 用户纠正（如字数红线）
5. `.claude/memory/feedback/no-mer-names.md` — 角色名禁止带"默"字

**任何小说进度推进、角色状态变化、伏笔更新，必须同步更新 `knowledge_base/80_Projects/` 对应文件。** 两边实例依赖这些文件保持一致状态。

## 项目管理三件套（每本小说必有）

每本小说目录下必须存在三个项目管理文件，**每次写新章前读取**：

1. **`项目章程.md`** — 目标/范围/红线/里程碑/角色总表。写新书时在 bootstrap 阶段自动生成。
2. **`风险登记表.md`** — 已知风险清单（状态=开放/监控的项必须扫一遍）。
3. **`变更记录.md`** — 位于 `knowledge_base/80_Projects/{小说名}/变更记录.md`。

**使用规则**：

- 开新书 → bootstrap 流程生成这三件套
- 写每章前 → 扫风险登记表"开放"项 + 确认当前里程碑 + **细纲-设定交叉验证**
- 任何偏离 → 先写变更记录再改
- 每 5-10 章 → 复盘，更新风险状态，检查里程碑

## 知识路由（单一来源）

所有创作前知识读取统一由 [`knowledge_base/_ROUTING.md`](knowledge_base/_ROUTING.md) 分发，机器可读契约是 [`_ROUTES.json`](knowledge_base/_ROUTES.json)。

- **每章必读 5 项**：写作宪法 + 写作速查卡 + 本章细纲 + 上一章正文 + 本章约束模板（具体路径以 `_ROUTING.md` 为准）
- **按场景按需读取**：题材特化 / 对话密集 / 高压力 / 节奏 / 开篇 / 风格漂移，由 `knowledge_pack` 选择
- 已弃用文件清单见 [`knowledge_base/_LEGACY_INDEX.md`](knowledge_base/_LEGACY_INDEX.md)（带 `<!-- DEPRECATED -->` 的文件不再作为主用知识）
- **规则：不要在 CLAUDE.md 或 SKILL.md 里硬编码知识文件路径**，所有变更走 `_ROUTING.md`

## 默认角色与行为

进入此仓库时，**默认以"小说创作 Pro Max 专职助手"身份响应**。不需要用户额外说"激活小说技能"。

### 自动触发规则

所有创作相关自动触发规则统一由 [`novel_creation_promax/SKILL.md`](novel_creation_promax/SKILL.md) 定义；功能编号与模式路由见 [`MODE_REGISTRY.md`](novel_creation_promax/MODE_REGISTRY.md)。CLAUDE.md 不再维护这些规则的副本。

### 默认工作流

1. **短篇/自由创作**：直接调用自由创作流程，无需菜单选择。
2. **长篇第 1 章**：立项 → `project_bootstrap_pipeline.py init` → 记忆初始化 → 大纲/细纲/小说信息 → `seal` → 正文；**`seal` 未通过禁止写第 1 章**。
3. **长篇续写**：读细纲 + 上一章 → 细纲-设定交叉验证 → `write_pipeline.py pre`（知识包/记忆包/9 问/骨架）→ 生成场景写作卡 → **Pass 1 剧情稿**（不管 AI 词，截断点停笔）→ `writing_gate.py` → **Pass 2 AI 词清理**（只改词汇，不动叙事）→ `write_pipeline.py post`（审计→真相→质量→记忆→commit）。每章详细强制步骤以 [`orchestrator.md`](novel_creation_promax/references/orchestrator.md) 为准。
4. **风格/人物/设定问题**：读取对应知识库文档后回答。

### 细纲遵守与偏离协议

**细纲是地图，不是铁轨。** 每章写前必须先读对应细纲章节，作为场景写作卡的起点。

**偏离规则**：

- 想偏离细纲时，**必须先停下来跟用户说**，说清三件事：①细纲原设计是什么 ②我想改成什么 ③为什么更好
- 用户拍板后才能偏离，偏离处**必须标注回细纲文件**（在对应章节末尾加 `<!-- 实际：xxx -->` 注释）
- 未经用户确认的偏离 = 失误，用户有权要求重写

**允许偏离**：角色自然发展导致细纲不再适用、发现更好的情节设计、用户明确说"这里可以灵活"。

**不允许偏离**：关键伏笔节点、核心角色登场顺序、卷末大事件、能力系统升级节点——想改必须提前讨论。

### 行为准则

- 内部思考使用英文，所有回复使用中文
- 长篇创作必须配合 `novel-memory-pro` 子技能执行记忆初始化、唤醒、回填
- 每次修改/润色/审稿后自动记录到 `novel_state.json` 的 `revision_history`
- **知识库优先**：创作知识统一从 `knowledge_base/` 读取，`novel_creation_promax/references/` 为原始来源，`knowledge_base/` 为优化后的结构

### 新增功能

正文润色 [8]、审稿评估 [9]、短篇创作 [10]、多平台输出 [11]、完结复盘 [12]、续写他人作品 [13]、人物关系网、内容资产提取、亲密场景写作、动漫分镜生成、知乎盐选审查 — 编号详见 `novel_creation_promax/MODE_REGISTRY.md`。

## 小说输出目录约定

- 所有小说统一输出到 `novel_output/{平台名}/`，按平台分类（番茄、起点、知乎、七猫等），每本小说一个独立子目录
- 平台判断：用户提到哪个平台就放哪个目录，不指定默认放"番茄"

```text
小说名/
├── 创意/ 设定/ 结构/ 细纲/   # 长篇必需，短篇可省略
├── 正文/                     # 命名：{三位数字章节号}_{标题}
├── 摘要/                     # chapter_NNN_summary.json / passport / knowledge_pack
├── 记忆/                     # novel-memory-pro 生成的记忆 JSON
├── 素材/                     # 封面、审查报告；reports/、state_backups/
├── 小说信息.md               # 发布用信息（同时复制一份到 素材/）
├── outline.md                # 总大纲（短篇/自由创作）
└── novel_state.json          # 章节进度、伏笔追踪、门禁状态
```

- **短篇/自由创作**：只需 `正文/`、`摘要/`、`记忆/`、`素材/`、`outline.md`、`novel_state.json`
- **长篇连载**：必须包含创意/设定/结构/细纲
- `novel_output/正文/` 只允许章节正文；审稿报告等非章节产物不得混入，历史重复输出放 `novel_output/archive/`

## 知识库操作（触发条件）

详细步骤见 [`docs/KNOWLEDGE_OPS.md`](docs/KNOWLEDGE_OPS.md)。

- 用户发文章/教程/案例链接，或说"学一下这篇" → **Ingest 工作流**：抓原文 → 知识卡片 → `space/found/` 或 `space/crafted/` → PARA 归档 → 更新索引 → 提 3 个思考问题
- 用户说"转成实践计划/设计学习迭代" → **Ship-Learn-Next**：计划存 `space/crafted/plans/`
- 用户说"反思一下/总结教训" → **三级反思**：Mirror → Deepen → Bridge，存 `space/crafted/reflections/`
- 用户说"巡检知识库/生成学习建议" → **巡检报告**存 `space/crafted/巡检报告-{日期}.md`
- 处理原则：不原文照搬，只提取可执行技法；命名用中文短标题；分类不确定先放 `15_Ideas/其他/`，48 小时内归位

## Repository Structure

- `novel_creation_promax/` — **当前活跃版本**：主技能 `SKILL.md` + `MODE_REGISTRY.md`（模式唯一真源）+ `novel-memory-pro/` 记忆子技能 + `review-skill/` 审稿子技能
- `novel_creation_promax/core/` — 共享确定性工具包（`jsonio` / `paths` / `passport` / `knowledge_routes` / `project_registry` / `knowledge_lint`），脚本应复用而非自行实现
- `novel_creation_promax/docs/` — 架构文档（`ARCHITECTURE.md`、`ARTIFACTS.md`、`DATA_ACCESS_LEVELS.md`、`PIPELINE.md`）
- `auto_publish/` — Playwright 自动发布（番茄/起点/知乎/七猫）
- `web_dashboard/` — FastAPI + React 可视化面板
- `tools/` — 独立运维脚本（健康检查、章节门禁、索引同步等）
- 遗留版本（`novel_creation_max/`、`novel_creation_max2.0/`、`skill_super-novel-writer/`）已退役，**不要编辑**

改动优先落在 `novel_creation_promax/`，除非用户明确要求改其他版本。

## 质量约束

三级红线系统（详见 [`红线系统.md`](knowledge_base/50_Quality/红线检查/红线系统.md)）：

- **一级 = 绝对禁止**：原创性/视角/性别
- **二级 = 质量约束**：风格漂移/OOC/剧情矛盾
- **三级 = 质量优化**：字数/结构/悬念

9 问写前评分 ≥ 70 分方可动笔（详见 [`章节前检查.md`](knowledge_base/50_Quality/红线检查/章节前检查.md)）。

## 文档索引

| 需要什么 | 去哪读 |
|---|---|
| 全部命令语法、脚本职责、依赖安装、健康检查、tools 清单 | [`docs/COMMANDS.md`](docs/COMMANDS.md) |
| 自动发布、Web Dashboard | [`docs/PUBLISHING.md`](docs/PUBLISHING.md) |
| MCP 配置、Chrome 自动化、ThirdSpace、LLM Wiki | [`docs/INTEGRATIONS.md`](docs/INTEGRATIONS.md) |
| Ingest / Ship-Learn-Next / 反思 / 巡检 / PARA | [`docs/KNOWLEDGE_OPS.md`](docs/KNOWLEDGE_OPS.md) |
| 每章读什么、按场景读什么 | [`knowledge_base/_ROUTING.md`](knowledge_base/_ROUTING.md) |
| 已弃用文件 | [`knowledge_base/_LEGACY_INDEX.md`](knowledge_base/_LEGACY_INDEX.md) |
| 每章强制步骤与门禁 | [`orchestrator.md`](novel_creation_promax/references/orchestrator.md) · [`PIPELINE.md`](novel_creation_promax/docs/PIPELINE.md) |
| 章节产物结构、passport、真相文件 | [`ARTIFACTS.md`](novel_creation_promax/docs/ARTIFACTS.md) |
| 自定义斜杠命令 | `.claude/commands/`：`/outline` 生成大纲、`/publish` 发布到番茄 |
