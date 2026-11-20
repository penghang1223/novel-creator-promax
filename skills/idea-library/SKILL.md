---
name: idea-library
description: 长期创意库管理。用户说“创意库”“以前想过什么”“查重”“归档创意”“整理创意”“调研库”时使用。负责查重、归档、索引、搜索和重建；不写正文、不改创意内容。
---

# 长期创意库

## 职责

管理 `${CLAUDE_PROJECT_DIR}/创意库/`：

- 查重：新创意/调研是否已经存在
- 归档：把定稿创意卡、调研报告复制进库
- 索引：维护 `_INDEX.md` 和 `_INDEX.json`
- 搜索：按标题、平台、题材、标签检索
- 重建：从文件恢复索引

不写正文、不改创意内容、不删除运行时产物。

## 库结构

```text
${CLAUDE_PROJECT_DIR}/创意库/
├── _SCHEMA.json       # 字段定义
├── _INDEX.json        # 机器索引
├── _INDEX.md          # 人读索引
├── 创意卡/
│   └── IDEA-YYYYMMDD-NNN_标题.md
└── 调研/
    └── RES-YYYYMMDD-NNN_标题.md
```

## 命令

```bash
# 初始化
python3 "${CLAUDE_PLUGIN_ROOT}/tools/idea_library.py" \
  --workspace "${CLAUDE_PROJECT_DIR}" init

# 搜索（平台/题材/标签可组合）
python3 "${CLAUDE_PLUGIN_ROOT}/tools/idea_library.py" \
  --workspace "${CLAUDE_PROJECT_DIR}" search --query "番茄 女频" --json

# 列出全部
python3 "${CLAUDE_PLUGIN_ROOT}/tools/idea_library.py" \
  --workspace "${CLAUDE_PROJECT_DIR}" list --json

# 归档批量创意卡：按 ## N. 拆成独立条目
python3 "${CLAUDE_PLUGIN_ROOT}/tools/idea_library.py" \
  --workspace "${CLAUDE_PROJECT_DIR}" archive-idea \
  --file "${CLAUDE_PROJECT_DIR}/创意/创意卡_2026-11-20.md" \
  --platform 番茄 --genre 女频 --split --status candidate

# 归档单篇创意
python3 "${CLAUDE_PLUGIN_ROOT}/tools/idea_library.py" \
  --workspace "${CLAUDE_PROJECT_DIR}" archive-idea \
  --file "${CLAUDE_PROJECT_DIR}/创意/某张卡.md" --title "书名" --score 88

# 归档调研报告
python3 "${CLAUDE_PLUGIN_ROOT}/tools/idea_library.py" \
  --workspace "${CLAUDE_PROJECT_DIR}" archive-research \
  --file "${CLAUDE_PROJECT_DIR}/素材/调研/2026-11-20_番茄_女频热门方向.md" \
  --platform 番茄 --genre 女频

# 从文件重建索引
python3 "${CLAUDE_PLUGIN_ROOT}/tools/idea_library.py" \
  --workspace "${CLAUDE_PROJECT_DIR}" rebuild-index
```

## 工作流

1. **查重**：生成新创意/调研前，先 `search` 标题、平台、题材、标签。
2. **判断**：已有相似条目时，先给用户看旧条目，问“扩写/换切口/新建”，不要直接重复生成。
3. **归档**：用户选定或定稿后，`archive-idea` / `archive-research`。
4. **确认**：返回 `archived` 或 `duplicate`；duplicate 时说明已有 ID，不覆盖。
5. **索引**：工具自动更新 `_INDEX.json` / `_INDEX.md`；手工改过文件后跑 `rebuild-index`。
6. **状态**：用户选定准备立项的创意，可把 `status` 改为 `selected`；放弃的改为 `archived`。

## 元数据

创意卡：

```yaml
id: IDEA-20261120-001
title: 她只想退休，却被推上凤位
type: idea
platform: 番茄
genre: 女频
tags: [宫斗, 退休, 反差]
score: 88
status: candidate | selected | archived
summary: 一句话概述
source: 创意/创意卡_2026-11-20.md
archived_at: 2026-11-20T...
content_hash: sha256
```

调研：

```yaml
id: RES-20261120-001
title: 番茄女频热门方向
type: research
platform: 番茄
genre: 女频
tags: [...]
source: 素材/调研/...
archived_at: ...
content_hash: sha256
```

## 硬规则

- 创意库只写工作区 `${CLAUDE_PROJECT_DIR}/创意库/`，不写插件 `knowledge_base/`。
- 归档是复制，不删除 `创意/` 和 `素材/调研/` 的原始产物。
- 查重用 `content_hash` 和规范化标题；重复时不覆盖，返回已有 ID。
- 批量创意卡用 `--split`，每个 `## N. 标题` 一个条目；不要把整份报告当一个创意。
- ID 稳定：`IDEA-YYYYMMDD-NNN` / `RES-YYYYMMDD-NNN`；不要手工改 ID。
- 不虚构分数、平台、题材；缺元数据时留空或问用户。
- 索引文件自动生成，不手工维护。

## 边界

- 不生成新创意；生成走 `novel-idea`。
- 不写调研报告；调研走 `novel-market-research`。
- 不替代 `80_Projects` 的项目记忆；创意库是选题沉淀，不是项目状态。
