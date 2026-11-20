---
name: novel-project-planning
description: 新书立项、世界观和人物设定、长篇大纲、分卷及章节细纲的专属技能。用户说“立项”“新书”“设定”“生成大纲”“分卷”“细纲”或需要修改这些规划资产时使用；负责完成 bootstrap/seal 交接，但不写正文。
---

# 小说立项与规划

## 边界

拥有创意、设定、结构、细纲和长篇正文许可的准备工作；止步于 `seal`，不代替章节写作流程。

| 输入 | 输出 | 验收 |
|---|---|---|
| 用户创意、目标平台、题材、已有项目资料 | 创意/设定/结构/细纲、项目管理三件套、真相文件 | `project_bootstrap_pipeline.py seal` 通过 |
| 已有大纲或设定 | 有理由的增量修改和变更记录 | 受影响细纲与真相文件一致 |

## 执行

1. 读取 [`../MODE_REGISTRY.md`](../MODE_REGISTRY.md) 和 [`../references/orchestrator.md`](../references/orchestrator.md) 的 Stage 1–4；阶段顺序和用户确认规则只以编排器为准。
2. 新书先读平台规则、角色库、对应题材包、`30_Plot` 的大纲/节奏/伏笔文件和质量红线；已有项目先读项目章程、风险登记表、变更记录及当前设定。
3. 新建长篇时运行：

   ```bash
   python3 novel_creation_promax/scripts/project_bootstrap_pipeline.py init --platform "{平台}" --title "{书名}" --genre "{题材}" --premise "{核心设定}"
   ```

4. 按 Stage 1–4 生成或更新规划资产。任何主线、人物动机、能力、卷结构的实质变更，先写入 `knowledge_base/80_Projects/{书名}/变更记录.md`。
5. 完成后运行：

   ```bash
   python3 novel_creation_promax/scripts/project_bootstrap_pipeline.py seal --novel-dir "novel_output/{平台}/{书名}"
   ```

6. `seal` 未通过时只修复报告列出的规划缺口；通过后交接书名、项目目录、当前细纲和 `can_write_chapter=true` 给章节流程。

## 禁止事项

- 不因 `init` 已创建目录就跳过知识库预读、8 卷细纲或最终复核。
- 不创建正文、不伪造 `workflow_gate`，也不以口头确认代替 `seal`。
- 不把细纲当成高于设定底座的真源；发现冲突时按变更协议处理。
