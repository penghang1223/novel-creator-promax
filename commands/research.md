---
description: 调研平台热门写作方向、榜单题材与差异化机会
argument-hint: "[平台] [题材/受众] [时间窗口]"
---

读取并执行 `${CLAUDE_PLUGIN_ROOT}/skills/novel-market-research/SKILL.md`。

要求：

- 平台未指定时先问一次，不要默认番茄。
- 结论区分 `[事实]`、`[推断]`、`[建议]`、`[待验证]`，外部结论带 URL 与访问日期。
- 报告写入 `${CLAUDE_PROJECT_DIR}/素材/调研/`。
- 结尾给 3–5 个可执行选题和下一步 `/novel-creator-pro:idea` 命令。
