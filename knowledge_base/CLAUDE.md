# 知识库内部索引

> 本文件为 `knowledge_base/` 内部的快速参考。**全局行为规则见项目根目录 `CLAUDE.md`**。

## PARA 编号体系

| 编号 | 目录 | 内容 |
|---:|---|---|
| 10 | `10_WorldBuilding/` | 世界观、题材知识库（都市/科幻/仙侠/玄幻/悬疑/言情/历史/大女主/惊悚/无限流/游戏/灵异/百合） |
| 15 | `15_Ideas/` | 创意方案（先按平台、再按题材） |
| 20 | `20_Characters/` | 角色命名指南、角色原型、人物设定技巧 |
| 30 | `30_Plot/` | 大纲模板、结构设计、伏笔设计、连贯性机制 |
| 40 | `40_Writing/` | 写作技巧、风格指南、开头钩子、降低AI痕迹、短篇模板、工作流 |
| 50 | `50_Quality/` | 红线系统、章节前检查、评估系统 |
| 60 | `60_Platform/` | 平台规则（番茄/起点/晋江/七猫/飞卢） |
| 70 | `70_Corpus/` | 人名数据库、毒舌语料、神回复语料 |
| 80 | `80_Projects/` | 项目级知识（每本小说一个子目录） |

目录治理契约见 `_STRUCTURE.json`。编号目录只表达知识域，不直接表达内容生命周期；生命周期由 `00_Inbox/`、活动域、`space/` 和历史归档边界共同表达。

## 路由

所有创作前知识读取统一由 `_ROUTING.md` 分发。已弃用文件见 `_LEGACY_INDEX.md`。

## Space/Vault

- `space/crafted/` — 原创内容（思考、创作、复盘）
- `space/found/` — 收集内容（外部文章、教程、案例分析）
- `space/crafted/plans/` — Ship-Learn-Next 实践计划
- `space/crafted/reflections/` — Mirror → Deepen → Bridge 反思
- `flux/` — 原始数据（Git 忽略）

## 项目目录契约

`80_Projects/` 每个项目至少保留 `_config.md`、`项目索引.md`、`变更记录.md`、`伏笔追踪/`、`角色状态/`、`剧情节点/`。项目编号或历史目录发生漂移时，使用 `_PROJECT_ALIASES.json`，不要直接重命名目录。

## 生命周期边界

- `00_Inbox/` 只做临时收件，整理后必须移出。
- `90_Archive/` 是历史兼容区，新内容不得继续写入；`惊鸿归档/` 和 `40_Writing_写作技巧/` 已迁入此处。
- 历史目录迁移必须先运行 `python tools/archive_knowledge.py` dry-run，再运行 `python tools/knowledge_base_audit.py` 验证。
