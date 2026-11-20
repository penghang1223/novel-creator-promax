---
name: novel-knowledge-ingestion
description: 把写作教程、平台规则、爆款案例、文章链接或用户材料提炼成可执行知识并归档。用户说“学一下这篇”“分析这个链接”“入库”“提炼写作方法”时使用。不改小说项目正文。
---

# 小说知识摄入

读取并严格执行：

1. `${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/knowledge-ingestion/SKILL.md`
2. `${CLAUDE_PLUGIN_ROOT}/knowledge_base/_ROUTING.md`

## 边界

- 原始素材、知识卡片和索引更新写入工作区 `knowledge_base/`。
- 不原文照搬，只提取可执行技法。
- 分类不确定先放 `15_Ideas/其他/`，48 小时内归位。
- 不修改小说正文、设定或流水线状态。
