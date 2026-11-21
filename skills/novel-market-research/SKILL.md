---
name: novel-market-research
description: 平台热门写作方向调研、市场趋势、榜单题材和赛道分析。用户说“最近什么题材火”“调研一下番茄/起点/知乎/七猫”“平台热门方向”“市场怎么样”“这个方向还能写吗”时使用。输出带来源和日期的可执行选题情报。
---

# 平台热门写作方向调研

目标不是写一篇趋势综述，而是产出**能直接指导选题和开篇的情报**。

## 工作区确认（写入前）

本技能会写 `素材/调研/` 和 `创意库/`。写入前运行：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/workspace.py" --workspace "${CLAUDE_PROJECT_DIR}" status --json
```

- `dangerous=plugin_root|root`：停止，不得写入。
- `confirmed=false` 且 `legacy_books=0`：展示 `workspace` 绝对路径与 `write_paths`，等用户确认后运行 `workspace.py confirm`。
- `confirmed=false` 且 `legacy_books>0`：运行 `workspace.py confirm --legacy` 后继续。
- `confirmed=true`：继续。

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

## 调研范围（scope）

先从任务提取 scope，并在报告开头写明：

| scope | 用途 | 重点 |
|---|---|---|
| `short-story` | 短篇/短故事/知乎盐选 | 钩子、情绪升级、反转铺垫、结尾兑现 |
| `long-project` | 长篇立项/开书 | 卖点、黄金三章、持续冲突、连载空间 |
| `genre-analysis` | 题材/赛道分析 | 受众、常见机制、同质化、差异化 |

同时记录平台、题材、读者、篇幅、已有创意和待验证问题。缺失信息先用上下文和项目默认值并记录假设；只有影响方向且不能推断时才询问。

## 复用与更新

- 先查 `${CLAUDE_PROJECT_DIR}/创意库/` 和 `素材/调研/` 是否已有同平台/同题材报告。
- 平台规则必须实时核查；已有样本可以保留，但要注明更新范围和是否仍覆盖本次题材。
- 不重复无关调研；旧本地趋势资料不能代替当前平台规则。

## 样本拆解

- 默认至少 3 篇不同作品，优先同平台、同题材、近 90 天可访问样本；不足时扩大时间范围并注明。
- 短篇：拆开场钩子、情绪升级、反转铺垫、结尾兑现与余味。
- 长篇：看卖点、黄金三章、持续冲突和连载空间。
- 题材分析：比较受众、常见机制、同质化程度和差异化空位。
- 未读结尾不能评价回收完整性；检索摘要只用于发现来源。

## 来源表

每条来源记录：标题、作者或机构、URL、发布日期（未知则注明）、访问日期、实际阅读范围。第三方解读不能代替官方确认。

## 读者反馈与证据限制

- 收集可访问评论中的具体期待或不满，区分“评论观察”和“调研者推断”；没有评论就记录缺口。
- 没有可靠数据时，不标“爆款”，不推断销量、签约率或转化率。
- 不绕过付费或访问限制；来源不足时给出缺口和可继续的策划范围，不宣称调研完成。

## 分析框架

1. 平台机制与读者耐心：推荐机制、弃书节点、更新要求、审核尺度。
2. 热门方向 Top 5：按证据强度分强/中/弱，不能只列题材名。
3. 情绪价值与爽点结构：读者追更到底图什么。
4. 标题 / 简介 / 开篇三章钩子：给出可复用句式，不抄具体作品标题。
5. 竞争密度与同质化：哪里已经挤满，哪里还有空位。
6. 差异化机会 3–5 条：每条说明“为什么现在能做”。
7. 风险：审核、版权、生命周期、执行难度。
8. 可执行选题 3–5 个：每个含 logline、目标读者、差异化、风险、下一步验证。

## 决策落点

报告必须至少给出 3 条“证据 → 判断 → 采用/避开 → 具体落点”，例如：

```text
[证据] 近 90 天同题材样本前 3 章都在第 2 章给出能力展示
[判断] 慢热开篇在该平台留存风险高
[采用] 第 2 章设置一次能力兑现
[落点] 第 2 章场景 3：主角第一次公开使用能力并付出代价
```

只提炼技法，不移植独特桥段、人物组合或原句。

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
- 来源不足或未读完整样本时，明确写缺口，不宣称调研完成。
- 不虚构评论、热度、销量、签约率或转化率。
- 结论必须落到“可写什么、怎么写开篇、风险是什么”，不能停在“这个题材很火”。
