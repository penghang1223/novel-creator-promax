---
name: novel-review
description: 单章精审和批量快审。用户说“审一下”“帮我看看这章”“质量怎么样”“审查”时使用。输出审稿报告，不直接改正文。
---

# 小说审稿

读取并严格执行：

1. `${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/review-skill/SKILL.md`
2. `${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/MODE_REGISTRY.md` 的 `review` 模式
3. `${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/docs/PIPELINE.md` 的失败处理

## 边界

- 审稿报告写入工作区 `素材/`，不写入插件目录。
- 不绕过硬审计，不直接改正文。
- 审稿发现 blocking 问题时，明确列出位置、证据和修复方向。
