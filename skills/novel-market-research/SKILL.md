---
name: novel-market-research
description: 平台热门写作方向调研、市场趋势、榜单题材和赛道分析。用户说“最近什么题材火”“调研一下番茄/起点/知乎/七猫”“平台热门方向”“市场怎么样”“这个方向还能写吗”时使用。输出带来源和日期的可执行选题情报。
---

# 平台热门写作方向调研

目标不是写一篇趋势综述，而是产出**能直接指导选题和开篇的情报**。

## 输入

先确认四项，缺平台时只问一次，不要默认：

- 平台：番茄 / 起点 / 知乎盐选 / 七猫 / 多平台对比
- 时间窗口：默认近 30 天
- 范围：题材、男频/女频、篇幅
- 用途：开新书 / 评估现有创意 / 平台选择

## 必读基线

1. `${CLAUDE_PLUGIN_ROOT}/knowledge_base/60_Platform/平台热门趋势.md`
2. `${CLAUDE_PLUGIN_ROOT}/knowledge_base/60_Platform/网文市场调研2026Q2.md`
3. `${CLAUDE_PLUGIN_ROOT}/knowledge_base/60_Platform/_PROFILES.json`
4. 对应平台报告（存在则读）：
   - `${CLAUDE_PLUGIN_ROOT}/knowledge_base/60_Platform/番茄商业情报2025.md`
   - `${CLAUDE_PLUGIN_ROOT}/knowledge_base/60_Platform/知乎盐选策划框架.md`
   - `${CLAUDE_PLUGIN_ROOT}/knowledge_base/60_Platform/七猫小说_创意策划方案_基于望舒调研_20260425.md`
5. 题材画像：`${CLAUDE_PLUGIN_ROOT}/knowledge_base/10_WorldBuilding/题材知识库/{题材}.md`

## 联网校验

- 用 WebSearch / WebFetch（或用户指定的浏览工具）查当前榜单、平台公告、征文活动和近期讨论。
- 每条外部结论记录 **URL + 访问日期**。
- 不得编造榜单名次、阅读量、稿费数字；无法联网时明确写“仅知识库基线，未联网校验”。
- 区分 `[事实]`、`[推断]`、`[建议]`、`[待验证]`。

## 分析框架

1. 平台机制与读者耐心：推荐机制、弃书节点、更新要求、审核尺度。
2. 热门方向 Top 5：按证据强度分强/中/弱，不能只列题材名。
3. 情绪价值与爽点结构：读者追更到底图什么。
4. 标题 / 简介 / 开篇三章钩子：给出可复用句式，不抄具体作品标题。
5. 竞争密度与同质化：哪里已经挤满，哪里还有空位。
6. 差异化机会 3–5 条：每条说明“为什么现在能做”。
7. 风险：审核、版权、生命周期、执行难度。
8. 可执行选题 3–5 个：每个含 logline、目标读者、差异化、风险、下一步验证。

## 输出位置

使用模板：

`${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/references/templates/market_research_report.md`

| 产物 | 路径 |
|---|---|
| 调研报告 | `${CLAUDE_PROJECT_DIR}/素材/调研/{YYYY-MM-DD}_{平台}_热门方向.md` |

**不要写入** `${CLAUDE_PLUGIN_ROOT}/knowledge_base/`。插件知识库是只读资产，更新时会被替换。

## 长期创意库

调研报告和创意卡共用工作区长期库：`${CLAUDE_PROJECT_DIR}/创意库/`。

| 层 | 路径 | 作用 |
|---|---|---|
| 本次运行产物 | `${CLAUDE_PROJECT_DIR}/素材/调研/` | 本轮调研报告 |
| 长期创意库 | `${CLAUDE_PROJECT_DIR}/创意库/调研/` | 去重、带 ID、可搜索的调研沉淀 |

调研前先查已有报告：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/idea_library.py" --workspace "${CLAUDE_PROJECT_DIR}" \
  search --query "{平台} {题材}" --json
```

定稿后归档：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/idea_library.py" --workspace "${CLAUDE_PROJECT_DIR}" \
  archive-research --file "${CLAUDE_PROJECT_DIR}/素材/调研/{YYYY-MM-DD}_{平台}_热门方向.md" \
  --platform "{平台}" --genre "{题材}"
```

库索引：`${CLAUDE_PROJECT_DIR}/创意库/_INDEX.md`；归档只复制，不删除原始报告。

报告结尾必须给下一步：

```text
下一步：/novel-creator-pro:idea {平台} {题材} {数量}
```

## 硬规则

- 平台未定先问，不要默认番茄。
- 没有来源的热门方向标 `[待验证]`，不得说成事实。
- 知识库数据必须标注最后更新时间，不得伪装成当日行情。
- 不复制榜单正文或他人简介，只提炼结构。
- 结论必须落到“可写什么、怎么写开篇、风险是什么”，不能停在“这个题材很火”。
