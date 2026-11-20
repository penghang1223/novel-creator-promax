---
name: novel-creator
description: |
  中文网文创作总入口。用户要立项、生成大纲/细纲、写章、续写、审稿、润色、记忆管理、知识摄入或多平台发布时使用。
  只负责路由和全局契约，不直接写正文。
---

# 小说创作 Pro Max（插件入口）

## 根目录约定（必须遵守）

- **插件资产**：`${CLAUDE_PLUGIN_ROOT}`，只读。技能、参考、知识库、脚本都在这里。
- **用户工作区**：`${CLAUDE_PROJECT_DIR}`，可写。`novel_output/`、`MEMORY.md`、`.claude/memory/` 都在这里。
- **禁止写入插件目录**：插件更新后旧目录会被清理，写进去的状态会丢。

所有命令使用绝对路径：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/scripts/write_pipeline.py" \
  --novel-dir "${CLAUDE_PROJECT_DIR}/novel_output/番茄/书名" \
  --chapter 1 --title "第1章"
```

## 启动时先读

1. `${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/MODE_REGISTRY.md` — 功能编号与模式路由
2. `${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/SKILL.md` — 全局契约与交接规则
3. 按任务读 `${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/references/orchestrator.md` — 阶段、门禁、裁决顺序

不要一次性加载全部子技能和知识包；按 `MODE_REGISTRY.md` 命中后再读。

## 路由

| 请求范围 | 子技能 |
|---|---|
| 平台热门方向、榜单题材、市场调研 | `novel-market-research` |
| 创意生成、脑洞、选题、创意卡 | `novel-idea` |
| 新书立项、设定、大纲、分卷、细纲 | `novel-project-planning` |
| 写章、续写、短篇、润色 | `novel-chapter-write` |
| 记忆初始化、唤醒、回填、体检 | `novel-memory` |
| 单章精审、批量快审 | `novel-review` |
| 格式转换、同步草稿、平台发布 | `novel-publish` |
| 学习文章、教程、案例链接 | `novel-knowledge-ingestion` |
| 环境、依赖、插件资产体检 | `novel-doctor` |

## 全局契约

- 长篇第 1 章前必须完成立项 `seal`；`seal` 未通过禁止写第 1 章。
- 章节状态唯一真源：`摘要/chapter_NNN_passport.json` + `素材/commits/`。
- 细纲是地图不是铁轨；偏离前必须向用户说明原设计、改动和理由。
- 任何章节推进、角色状态、伏笔变化，必须同步工作区的项目记忆与 `knowledge_base/80_Projects/`。
- 原创性、视角、性别红线为一级禁止；违反即停。
- 写完后运行完整性校验：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/verify_project_integrity.py" \
  --novel-dir "${CLAUDE_PROJECT_DIR}/novel_output/番茄/书名"
```

## 用户偏好

用户偏好和纠正存放在工作区 `.claude/memory/`；启动时如存在则读取，不要用对话摘要替代文件状态。
