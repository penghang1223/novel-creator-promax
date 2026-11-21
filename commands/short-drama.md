---
description: 评估小说能否改编短剧/漫剧，并输出分集大纲、钩子表和风险清单
argument-hint: "[书名] [全本|前N章|某卷] [竖屏短剧|漫剧|中剧]"
---

读取并执行 `${CLAUDE_PLUGIN_ROOT}/skills/short-drama-adaptation/SKILL.md`。

要求：

- 按 `短剧改编10维.md` 逐维评估，每维给原文证据。
- 只做改编设计，不改正文、不改设定。
- 产物写入 `${CLAUDE_PROJECT_DIR}/素材/短剧/{书名}/`。
- 不承诺平台采购、保底或收益；需要改正文时列出前置修改清单，交回写章流程。
