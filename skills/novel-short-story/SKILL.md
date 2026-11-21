---
name: novel-short-story
description: 短篇、短故事、知乎盐选等整篇创作。用户说“写个短篇”“短故事”“知乎盐选”“整篇审稿”时使用。组织调研、策划、写前检查、两遍写作和整篇审稿；已有长篇的下一章仍走写章流水线。
---

# 短篇创作

## 边界

| 拥有 | 不拥有 |
|---|---|
| 短篇项目的组织、写前检查、整篇验收 | 长篇章节状态机、独立短篇 seal、发布授权 |

- 调研交给 `${CLAUDE_PLUGIN_ROOT}/skills/novel-market-research/SKILL.md`，正文阶段复用编排器。
- 不新建独立章节状态机；已有合法 `seal` 的项目仍执行原章节门禁。
- 独立短篇使用人工写前检查与整篇审稿，不伪造 `workflow_gate`。
- 修改已有正文时交接 `${CLAUDE_PLUGIN_ROOT}/skills/novel-revision/SKILL.md`。

## 工作区确认

写入前运行：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/workspace.py" --workspace "${CLAUDE_PROJECT_DIR}" status --json
```

`dangerous=plugin_root|root` 时停止；未确认且无存量书时先让用户确认产物目录。

## 执行

1. 读取 `${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/references/short-story-workflow.md`，以其任务边界、写前检查、脚本适用范围和交付要求为准。
2. 明确任务：平台、题材、读者、整篇目标字数、分章方式、投稿/签约目标、创意与禁区。平台未定先问，不默认番茄。
3. 新作调用 `/novel-creator-pro:research`（scope=short-story），输出 `{小说目录}/素材/短篇调研.md`；已有报告先检查来源时效和题材覆盖，不重复无关调研。
4. 生成 `{小说目录}/outline.md`：一句话卖点、人物动机、完整因果链、先锁结局再倒推线索、开篇钩子与情绪节拍。
5. 完成 `{小说目录}/素材/短篇写前检查.md`：逐项写证据位置和通过/未通过，不得用空模板或“已检查”代替。
6. 两遍写作：Pass 1 完整行动与冲突 → 逻辑/人物/伏笔检查 → Pass 2 清理 AI 表达 → 整篇审稿。
7. 交付正文、outline、调研或豁免、写前检查、`素材/短篇审稿.md`，回填记忆与 `knowledge_base/80_Projects/`。

## 输出

```text
${CLAUDE_PROJECT_DIR}/novel_output/{平台}/{书名}/
├── 正文/
├── outline.md
└── 素材/
    ├── 短篇调研.md
    ├── 短篇写前检查.md
    └── 短篇审稿.md
```

## 硬规则

- 调研先行；纯练笔或用户明确跳过时记录豁免，不宣称完成市场验证。
- 先锁结局/谜底，再倒推铺垫；反转必须有前置依据。
- 整篇字数按短篇预算，不套用长篇单章 2800-3200 阈值。
- 独立短篇不伪造 `seal`、`workflow_gate`、审计通过或 commit。
- 交付前必须有写前检查和整篇审稿；阻断项未解决不得标为定稿。
- 摘要和状态变化同步项目记忆与 `knowledge_base/80_Projects/`，不把全文复制进知识库。

## 禁止事项

- 不把“进入短篇模式”理解为可以跳过调研和因果设计。
- 不伪造长篇 seal、审计通过或平台商业效果。
- 不把长篇细纲、八卷结构或单章阈值硬套到短篇。
- 不复制工作流的详细步骤到本技能；详细规则只在 `short-story-workflow.md` 维护。
