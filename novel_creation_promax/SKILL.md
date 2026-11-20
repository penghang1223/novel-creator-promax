---
name: novel-creation-promax
description: |
  中文网文创作的总路由技能。用于识别小说创作、立项、大纲、章节写作、记忆、审稿、知识摄入和多平台发布请求，并将任务交给正确的能力技能或受状态机保护的写作流水线。
---

# 小说创作 Pro Max

本技能只负责路由、全局约束和技能之间的交接；不重复定义各能力的执行细节。

## 先路由，再加载必要上下文

1. 先读取 [`MODE_REGISTRY.md`](MODE_REGISTRY.md)，按 `mode_key` 选择能力。
2. 只加载下表命中的技能或参考文件；不要把所有子技能和知识包一次性塞入上下文。
3. 需要跨能力交接时，以项目目录中的文件和 passport 为准，不以聊天摘要代替状态。

| 请求范围 | 负责入口 | 交接产物 | 不负责 |
|---|---|---|---|
| 新书立项、设定、大纲、分卷或细纲 | [`project-planning/SKILL.md`](project-planning/SKILL.md) | 创意/设定/结构/细纲、bootstrap gate | 正文写作 |
| 写章、续写、短篇、润色 | [`references/orchestrator.md`](references/orchestrator.md) Stage 5 + `write_pipeline.py` | 正文、摘要、passport、commit | 将步骤拆为更多 skill |
| 记忆初始化、唤醒、回填、阶段体检 | [`novel-memory-pro/SKILL.md`](novel-memory-pro/SKILL.md) | 记忆包、记忆 JSON、review pack | 正文改写 |
| 单章精审、批量快审 | [`review-skill/SKILL.md`](review-skill/SKILL.md) | 审稿报告 | 绕过硬审计或直接改稿 |
| 格式转换、同步草稿、平台发布 | [`publishing/SKILL.md`](publishing/SKILL.md) | 平台稿、同步/发布状态 | 未经授权的外部发布 |
| 学习文章、案例、教程或外部链接 | [`knowledge-ingestion/SKILL.md`](knowledge-ingestion/SKILL.md) | 原始素材、知识卡片、索引更新 | 项目正文或设定修改 |
| 题材分析、风格建议、角色问题 | `MODE_REGISTRY.md` 指定的知识库入口 | 咨询或约束清单 | 新建项目状态 |

## 全局契约

| 主题 | 唯一真源 |
|---|---|
| 功能编号和路由 | [`MODE_REGISTRY.md`](MODE_REGISTRY.md) |
| 阶段顺序、门禁、裁决优先级 | [`references/orchestrator.md`](references/orchestrator.md) |
| 章节状态和断点续跑 | `摘要/chapter_NNN_passport.json` + `write_pipeline.py` |
| 项目状态 | `novel_state.json` |
| 结构化故事事实 | `设定/真相文件/*.json` |
| 知识路由 | `knowledge_base/_ROUTES.json` |
| 用户偏好和纠正 | `.claude/memory/` |

- 子技能不得复制或改写章节状态机；写作、润色后的正文必须重新进入既有审计链。
- 子技能只写自己拥有的产物，跨域改动必须通过对应流水线或用户明确确认。
- 任何章节、角色状态或伏笔推进，必须同步项目记忆和 `knowledge_base/80_Projects/` 对应项目文件。
- 长篇第 1 章必须先由立项技能完成 `seal`；每章详细强制步骤只以编排器为准。
- `Pass 1 → Gate → Pass 2 → post` 是单一状态机内的连续阶段，不建立独立 skill。

## 常用入口

```bash
# 长篇立项完成后，运行 seal 取得正文许可
python3 novel_creation_promax/scripts/project_bootstrap_pipeline.py seal --novel-dir "novel_output/{平台}/{书名}"

# 每章的受保护入口
python3 novel_creation_promax/scripts/write_pipeline.py pre --novel-dir "{小说目录}" --chapter N --title "{标题}"
python3 novel_creation_promax/scripts/write_pipeline.py post --novel-dir "{小说目录}" --chapter N --title "{标题}"

# 技能与引用完整性检查
python3 novel_creation_promax/scripts/skill_health_check.py
```

目录与产物结构见 [`docs/ARTIFACTS.md`](docs/ARTIFACTS.md)，数据访问边界见 [`docs/DATA_ACCESS_LEVELS.md`](docs/DATA_ACCESS_LEVELS.md)。
