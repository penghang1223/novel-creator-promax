---
name: data-diagnosis
description: 上线后数据诊断入口。用户说“我扑了”“数据掉了”“断流”“要不要切书”“书测”时使用。先要 11 项数据，再调用 data_diagnosis.py；完整流程复用 novel-diagnose。
---

# 数据诊断（项目入口）

## 职责

本项目内的数据诊断入口。完整方法论和断流急救在插件技能 `novel-creator-pro:novel-diagnose`；本 skill 负责把项目数据、平台口径和输出路径接起来。

## 必读

1. `${CLAUDE_PLUGIN_ROOT}/knowledge_base/60_Platform/数据诊断与救盘.md`
2. `${CLAUDE_PLUGIN_ROOT}/knowledge_base/60_Platform/平台机制与换挡.md`
3. `${CLAUDE_PLUGIN_ROOT}/skills/novel-diagnose/SKILL.md`（完整流程）
4. 当前项目 `novel_state.json`、`素材/audit_*.json`、章节摘要

## 工具

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/data_diagnosis.py" \
  --input "{数据文件}" --json \
  --output "${CLAUDE_PROJECT_DIR}/素材/诊断/{YYYY-MM-DD}_数据诊断.md"
```

数据文件支持 JSON 或 Markdown，至少包含总字数。

## 工作流

1. **先要数据，不给建议**。11 项：

```text
总字数 / 当前在读 / 书架比 / 追更比 / 前 10 章完读率 / 10 万字完读率 /
7 日追更人数 / 日均更新 / 断更天数 / 作品评分 / 点击率或曝光量
```

2. 确认平台和采集时间；不同平台阈值不同。
3. 运行 `data_diagnosis.py`，得到阶段、问题、处方、七天动作。
4. 按“先修最前端”解释：止血 → 门面 → 前 300 字 → 第一章 → 前三章 → 10 万字完读 → 长线结构。
5. 输出到工作区 `素材/诊断/`，并在 `novel_state.json` 记录最近一次诊断时间和结论。
6. 需要断流急救、书测、切书决策时，转到 `novel-creator-pro:novel-diagnose`。

## 输出格式

```text
数据诊断
- 平台 / 采集时间 / 总字数
- 阶段：L1-L6，当前唯一考核项
- 最严重 3 项：指标 / 实测 / 目标 / 严重度
- 处方：按优先级 1-3 条
- 七天动作：1 条主行动
- 报告：{路径}
```

## 硬规则

- 缺 11 项数据时不给处方；信息不足的建议一定是废话。
- 不把单个案例推广成整体结论。
- 不承诺流量、收益、签约结果。
- 七天里只动一件事，动三件就测不出因果。
- 引用数字必须带时间、单位、样本、口径、比较对象。
- 诊断报告只写工作区，不写插件知识库。

## 边界

- 不改正文、不改大纲、不改书名/封面；只给诊断和修复顺序。
- 不替代 `novel-doctor`（环境/产物一致性）和 `review`（内容质量）。
- 平台阈值以对应平台口径为准；番茄默认口径是 2026-08/09，过期要更新。
