# 知识库内部索引

> 本文件为 `knowledge_base/` 内部的快速参考。**全局行为规则见项目根目录 `CLAUDE.md`**。

## PARA 编号体系

| 编号 | 目录 | 内容 |
|---:|---|---|
| 10 | `10_WorldBuilding/` | 世界观、题材知识库（都市/科幻/仙侠/玄幻/悬疑/言情/历史/大女主/惊悚/无限流/游戏/灵异/百合） |
| 20 | `20_Characters/` | 角色命名指南、角色原型、人物设定技巧 |
| 30 | `30_Plot/` | 大纲模板、结构设计、伏笔设计、连贯性机制 |
| 40 | `40_Writing/` | 写作技巧、风格指南、开头钩子、降低AI痕迹、短篇模板、工作流 |
| 50 | `50_Quality/` | 红线系统、章节前检查、评估系统 |
| 60 | `60_Platform/` | 平台规则（番茄/起点/晋江/七猫/飞卢） |
| 80 | `80_Projects/` | 项目级知识（每本小说一个子目录） |

目录治理契约见 `_STRUCTURE.json`。本库为运行精简版，仅含 7 个知识域；收件箱、创意池、语料、原生空间与历史归档由全量库 novel-creator-pro 承担。

## 路由

所有创作前知识读取统一由 `_ROUTING.md` 分发。已弃用文件见 `_LEGACY_INDEX.md`。

能力包：`packs/<pack_id>/pack.json` 声明平台/题材信号、能力键、路由与坑点；`tools/pack_check.py` 校验。新增题材/平台只加包，不改 L0 脚本。

引擎方法（立项/开篇/量化门禁/六台账/数据诊断）统一索引入口：`40_Writing/引擎方法索引.md`；机器路由见 `_ROUTES.json` 的 `engine_*` 键。

## 项目目录契约

`80_Projects/` 每个项目先建 `_config.md`，立项后补齐项目索引、变更记录、伏笔追踪、角色状态、剧情节点。项目编号漂移登记到 `_PROJECT_ALIASES.json`，不重命名历史目录。

## 生命周期边界

- 本库为活动知识精简版，历史归档在全量库 novel-creator-pro 的 `90_Archive/`。
- 历史目录迁移先运行 `python tools/archive_knowledge.py` dry-run，再用 `python tools/knowledge_base_audit.py` 验证。
