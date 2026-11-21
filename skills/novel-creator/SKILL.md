---
name: novel-creator
description: |
  中文网文创作总入口。用户要立项、生成大纲/细纲、写章、续写、审稿、润色、记忆管理、知识摄入或多平台发布时使用。
  只负责路由和全局契约，不直接写正文。
---

# 小说创作 Pro Max

本技能只负责路由、全局约束和技能之间的交接；不重复定义各能力的执行细节。

## 根目录约定（必须遵守）

- **插件资产**：`${CLAUDE_PLUGIN_ROOT}`，只读。技能、参考、知识库、脚本都在这里。
- **用户工作区**：`${CLAUDE_PROJECT_DIR}`，可写。`novel_output/`、`${CLAUDE_PROJECT_DIR}/MEMORY.md`、`.claude/memory/` 都在这里。
- **禁止写入插件目录**：插件更新后旧目录会被清理，写进去的状态会丢。

所有命令使用绝对路径：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/scripts/write_pipeline.py" \
  --novel-dir "${CLAUDE_PROJECT_DIR}/novel_output/番茄/书名" \
  --chapter 1 --title "第1章"
```

## 先路由，再加载必要上下文

1. 先读取 `${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/MODE_REGISTRY.md`，按 `mode_key` 选择能力。
2. 只加载下表命中的技能或参考文件；不要把所有子技能和知识包一次性塞入上下文。
3. 需要跨能力交接时，以项目目录中的文件和 passport 为准，不以聊天摘要代替状态。

| 请求范围 | 负责入口 | 交接产物 | 不负责 |
|---|---|---|---|
| 平台热门方向、赛道趋势、市场调研 | `MODE_REGISTRY.md` 模式 14 | 调研报告 | 虚构数据、直接写正文 |
| 创意生成、脑洞、选题 | `MODE_REGISTRY.md` 模式 15 | 创意卡、五维评分 | 直接立项、写正文 |
| 项目阶段、下一步、阶段门禁 | `MODE_REGISTRY.md` 模式 16 | workflow.json、阶段状态 | 替代章节门禁 |
| 上线后数据、断流、切书、书测 | `novel-diagnose` + `${CLAUDE_PLUGIN_ROOT}/tools/data_diagnosis.py` | 诊断报告、七天动作 | 无数据就给处方、承诺收益 |
| 新书立项、设定、大纲、分卷或细纲 | `${CLAUDE_PLUGIN_ROOT}/skills/novel-project-planning/SKILL.md` | 创意/设定/结构/细纲、bootstrap gate | 正文写作 |
| 写章、续写、短篇、润色 | `${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/references/orchestrator.md` Stage 5 + `write_pipeline.py` | 正文、摘要、passport、commit | 将步骤拆为更多 skill |
| 记忆初始化、唤醒、回填、阶段体检 | `${CLAUDE_PLUGIN_ROOT}/skills/novel-memory/SKILL.md` | 记忆包、记忆 JSON、review pack | 正文改写 |
| 单章精审、批量快审 | `${CLAUDE_PLUGIN_ROOT}/skills/novel-review/SKILL.md` + `${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/references/review-result-schema.md` | 审稿 JSON、人读报告 | 绕过硬审计或直接改稿 |
| 格式转换、同步草稿、平台发布 | `${CLAUDE_PLUGIN_ROOT}/skills/novel-publish/SKILL.md` | 平台稿、同步/发布状态 | 未经授权的外部发布 |
| 学习文章、案例、教程或外部链接 | `${CLAUDE_PLUGIN_ROOT}/skills/novel-knowledge-ingestion/SKILL.md` | 原始素材、知识卡片、索引更新 | 项目正文或设定修改 |
| 题材分析、风格建议、角色问题 | `MODE_REGISTRY.md` 指定的知识库入口 | 咨询或约束清单 | 新建项目状态 |

## 全局契约

| 主题 | 唯一真源 |
|---|---|
| 功能编号和路由 | `${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/MODE_REGISTRY.md` |
| 阶段顺序、门禁、裁决优先级 | `${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/references/orchestrator.md` |
| 章节状态和断点续跑 | `摘要/chapter_NNN_passport.json` + `write_pipeline.py` |
| 项目状态 | `novel_state.json` |
| 结构化故事事实 | `设定/真相文件/*.json` |
| 写作任务书 | `摘要/chapter_NNN_taskbook.md` |
| 结构化审稿 | `摘要/chapter_NNN_review.json` |
| 知识路由 | `knowledge_base/_ROUTES.json` |
| 用户偏好和纠正 | `.claude/memory/` |

- 子技能不得复制或改写章节状态机；写作、润色后的正文必须重新进入既有审计链。
- 子技能只写自己拥有的产物，跨域改动必须通过对应流水线或用户明确确认。
- 任何章节、角色状态或伏笔推进，必须同步项目记忆和 `knowledge_base/80_Projects/` 对应项目文件。
- 长篇第 1 章必须先由立项技能完成 `seal`；每章详细强制步骤只以编排器为准。
- `rule_stack.write_ready=false`（存在 critical 未知事实）时禁止起草。
- `reviewer` 只返回 JSON，主流程负责落盘和校验；审稿存在 `blocker` 时 quality 与 commit 必须阻断。
- `Pass 1 → Gate → Pass 2 → post` 是单一状态机内的连续阶段，不建立独立 skill。

## 行为红线（随插件加载）

1. 写新章前必读：项目章程、风险登记表、本章细纲、上一章正文。
2. 细纲是地图不是铁轨：偏离前先说明原设计、改动和理由，确认后写回细纲注释。
3. 每章正文 2800-3200 中文字符（以平台档案为准）；不足时补观察、试探、交锋、代价、新线索。
4. 角色名禁止含「默」字。
5. 任何章节、角色或伏笔推进，同步工作区记忆与 `knowledge_base/80_Projects/` 对应文件。
6. 插件目录只读；正文、摘要、passport、commit 只写工作区。
7. 新增具名角色或为角色新增化名、外号时，必须先执行 `${CLAUDE_PLUGIN_ROOT}/skills/name-generator/SKILL.md`，实际运行命名脚本并检查禁字、撞名及同音冲突；立项、短篇、续写和改稿均适用。未完成命名检查和用户选定前，不得将候选名写入正文或正式设定；已有姓名沿用、用户指定姓名的处理以命名技能为准。

## 常用入口

```bash
# 长篇立项完成后，运行 seal 取得正文许可
python3 "${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/scripts/project_bootstrap_pipeline.py" seal \
  --novel-dir "${CLAUDE_PROJECT_DIR}/novel_output/{平台}/{书名}"

# 每章的受保护入口
python3 "${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/scripts/write_pipeline.py" pre \
  --novel-dir "${CLAUDE_PROJECT_DIR}/novel_output/{平台}/{书名}" --chapter N --title "{标题}"
python3 "${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/scripts/write_pipeline.py" post \
  --novel-dir "${CLAUDE_PROJECT_DIR}/novel_output/{平台}/{书名}" --chapter N --title "{标题}"

# 技能与引用完整性检查
python3 "${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/scripts/skill_health_check.py"
```

目录与产物结构见 `${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/docs/ARTIFACTS.md`，数据访问边界见 `${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/docs/DATA_ACCESS_LEVELS.md`。

## 用户偏好

用户偏好和纠正存放在工作区 `.claude/memory/`；启动时如存在则读取，不要用对话摘要替代文件状态。
