---
name: novel-review
description: 单章精审和批量快审。用户说“审一下”“帮我看看这章”“质量怎么样”“审查”时使用。输出结构化审稿 JSON 和人读报告，不直接改正文。
---

# 小说审稿

> **定位**：对已有章节做深度质量审查，不走写后审计的硬规则检查，而是用知识库原文作为评判标准做“人级”审查。
>
> **核心区别**：`post_write_audit.py` 是自动化规则匹配（AI词/字数/乒乓句），本技能是 LLM 驱动的深度判断（对话质感/爽点节奏/章节结构/去AI化/追读力）。

## 边界

拥有审稿标准、自动检测编排和审稿报告；输出问题、证据与修复建议，不拥有正文、细纲、记忆或发布状态。

- 审稿报告写入工作区 `素材/`，JSON 写入 `摘要/`，不写入插件目录。
- 不绕过硬审计，不直接改正文。

## 禁止事项

- 不以深度审稿替代 `post_write_audit.py` 等硬性门禁。
- 不在用户确认修复前直接覆盖正文。
- 不因审稿结论绕过细纲偏离协议、真相文件或章节 passport。
- reviewer 只生产 JSON；主流程不得替 reviewer 编造分数或问题。
- 契约校验失败时重新调用 reviewer，不得手改字段绕过。

## 输出契约（先看这个）

审稿结论分两层：

1. **机器层** `摘要/chapter_NNN_review.json`：由 `reviewer` 子代理返回，字段见 `${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/references/review-result-schema.md`。
2. **人读层** `{小说目录}/素材/审稿报告_chNNN.md`：由 `tools/review_result.py render` 从 JSON 生成，不参与门禁。

reviewer 只返回 JSON，不写文件；主流程负责校验、落盘和渲染。`blocking_count > 0` 时，`write_pipeline.py post` 的 quality 与 commit 阶段会阻断。

## 触发语

- “审一下第N章” / “这章写得怎么样” / “帮我审查这一章”
- “审一下第M-N章” / “审查一下这卷” / “全本审查”
- 写完一章后自动完成基础审计；仅在用户要求或基础审计问题较多时进入深度审稿

## 双审查模式

| 模式 | 触发语特征 | 范围 | 深度 |
|---|---|---|---|
| **单章精审** | 指定1章 | 1章 | 五维度逐项分析+具体段落引用 |
| **批量快审** | 指定多章/一卷 | 2-20章 | 每章快速扫描+跨章节分析 |

默认判断：提到具体章号且只有1个 → 单章精审。提到范围（第M-N章/这卷/全本）→ 批量快审。

## 单章精审

### Step 1：自动检测

运行自动化脚本获取硬性数据：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/scripts/post_write_audit.py" \
  --chapter-file "{小说目录}/正文/第N章-xxx.md" \
  --prev-file "{小说目录}/正文/第N-1章-xxx.md" \
  --title "第N章 xxx"
```

提取结果：AI词数量/黑名单词数量/字数/对话占比/乒乓句/钩子密度。

### Step 2：调用 reviewer 深度审查

必须使用 Agent 工具调用 `novel-creator-pro:reviewer`，不得由主流程口头代替。

调用前先取审稿目标与依据：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/review_result.py" target \
  --novel-dir "{小说目录}" --chapter N --json --ensure-revision --with-basis
```

把当前正文的 `target`（含 `revision_id`）、`basis` 和 `expected_versions` 传给 reviewer；reviewer 返回的 JSON 必须包含该 `target`，blocker/major 必须带 `source_refs` 原文引用。

主流程用 `save` 校验并写入 `摘要/chapter_NNN_review.json`：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/review_result.py" save \
  --novel-dir "{小说目录}" --chapter N --input /tmp/reviewer.json
```

正常流程不使用 `--bind-target`；它只用于 reviewer 无法计算哈希时的兜底。校验失败时重新调用 reviewer；不得手改字段绕过。若 `status=stale`，表示正文在审稿后已变化，必须重新审稿。

下面五段是 reviewer 的审查依据，主流程只用于核对 reviewer 是否覆盖全部维度。

**维度1：对话质感**
- 读取 `${CLAUDE_PLUGIN_ROOT}/knowledge_base/40_Writing/03_人物与对话/对话质感完整框架.md`
- 读取 `${CLAUDE_PLUGIN_ROOT}/knowledge_base/40_Writing/03_人物与对话/AI对话丰满化技法.md`
- 对照六要素：从正文抽取2-3段对话场景，逐项检查
- 声纹测试：删掉“某某说”能否分辨谁在说话
- 干涩检测5问：逐段回答
- 输出：X/10 + 具体问题

**维度2：爽点节奏**
- 读取 `${CLAUDE_PLUGIN_ROOT}/knowledge_base/40_Writing/04_场景与描写/爽点设计.md`
- 读取 `${CLAUDE_PLUGIN_ROOT}/knowledge_base/40_Writing/04_场景与描写/潜台词与张力技法.md`
- 检查：爽点有无/流水线是否走完/爽:压比例/潜台词/套路检测
- 对照 `${CLAUDE_PLUGIN_ROOT}/knowledge_base/40_Writing/06_质量校验/套路预判+绕开机制.md` 检测是否踩套路
- 输出：X/10 + 具体问题

**维度3：章节结构**
- 读取 `${CLAUDE_PLUGIN_ROOT}/knowledge_base/40_Writing/02_节奏与结构/每章节奏公式与卡章技巧.md`
- 读取 `${CLAUDE_PLUGIN_ROOT}/knowledge_base/40_Writing/02_节奏与结构/张力曲线设计.md`
- 检查：开头冲突/节奏模板/断章有效性/卡章公式/张力三层/高潮代价/余波
- 输出：X/10 + 具体问题

**维度4：去AI化**
- 读取 `${CLAUDE_PLUGIN_ROOT}/knowledge_base/40_Writing/05_降AI痕迹/降低AI痕迹.md`
- 检查：表层AI特征/结构层变化/认知层人味/“每段三刀”/红线检查
- 对照 `${CLAUDE_PLUGIN_ROOT}/knowledge_base/50_Quality/红线检查/红线系统.md` 检查红线
- 输出：X/10 + 具体问题

**维度5：追读力**
- 读取 `${CLAUDE_PLUGIN_ROOT}/knowledge_base/40_Writing/01_开篇技巧/开头钩子库.md`
- 检查：章末钩子强度/爽点兑现/微兑现债务堆积/情绪连贯/信息差利用
- 对照 `${CLAUDE_PLUGIN_ROOT}/knowledge_base/40_Writing/02_节奏与结构/strand节奏追踪.md` 检查 strand 分布
- 输出：X/10 + 具体问题

### Step 3：渲染报告

JSON 校验通过后，用确定性脚本渲染报告，不再手写 Markdown：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/review_result.py" render \
  --novel-dir "{小说目录}" --chapter N \
  --output "{小说目录}/素材/审稿报告_chNNN.md"
```

报告只展示 JSON 中的内容：五维评分、S/A/B/C/D 总评、按严重度排序的问题和修复建议。

### Step 4：用户确认

将审查报告输出给用户，等待确认：

- 用户说“修” → 按建议逐条修复，每条修复需用户确认
- 用户说“过” → 跳过修复，仅记录报告
- 用户说“重写” → 触发重写流程（回到写前检查）
- 修复后重新跑 Step 1 验证修复效果

## 批量快审

### Step 1：每章快速扫描（循环）

对每章依次执行：

1. 运行 `post_write_audit.py`
2. 对话质感速查（六要素覆盖率，~30秒判断）
3. 爽点速查（有无爽点，~15秒判断）
4. 结构速查（断章有效性，~15秒判断）
5. 追读力速查（章末钩子+债务堆积，~15秒判断）

每章输出：自动检测结果 + 5维度快速评分。

### Step 2：跨章节分析

1. 运行 `${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/scripts/plot_continuity_checker.py` → 伏笔回收/时间线/因果链
2. 运行 `${CLAUDE_PLUGIN_ROOT}/skills/novel-memory/scripts/character_consistency_checker.py` → 角色OOC
3. 张力曲线趋势：章节间张力是否合理起伏（对照5章张力模板：6/4/5/8-9/2-3）
4. 爽点密度：是否符合“每3章1中爽/每10章1大爽”
5. 追读力趋势：钩子类型分布、债务堆积趋势、情绪衔接是否断裂
6. Strand 分布：Quest/Fire/Constellation 比例是否均衡，是否触发断档预警
7. 套路重复检测：最近5章是否用了相同桥段

### Step 3：整体报告

按 `references/review-report-template.md` 的批量模板输出：

- 每章评分汇总表
- 跨章节问题汇总
- 重点关注清单（需要修复的章节+原因）

## 知识库集成

**审稿用知识库原文，不用速查卡。** 速查卡是写时快参照，审稿需要原文的完整规则+案例+检查清单。

| 审查维度 | 知识库文件 |
|---|---|
| 对话质感 | `40_Writing/03_人物与对话/对话质感完整框架.md` |
| 对话质感 | `40_Writing/03_人物与对话/AI对话丰满化技法.md` |
| 对话质感 | `40_Writing/03_人物与对话/人味写作指南.md` |
| 爽点节奏 | `40_Writing/04_场景与描写/爽点设计.md` |
| 爽点节奏 | `40_Writing/04_场景与描写/潜台词与张力技法.md` |
| 章节结构 | `40_Writing/02_节奏与结构/每章节奏公式与卡章技巧.md` |
| 章节结构 | `40_Writing/02_节奏与结构/张力曲线设计.md` |
| 去AI化 | `40_Writing/05_降AI痕迹/降低AI痕迹.md` |
| 追读力 | `40_Writing/01_开篇技巧/开头钩子库.md` |
| 追读力 | `40_Writing/02_节奏与结构/strand节奏追踪.md` |
| 套路检测 | `40_Writing/06_质量校验/套路预判+绕开机制.md` |
| 红线底线 | `50_Quality/红线检查/红线系统.md` |

## 参考文件

- [references/review-dimensions.md](references/review-dimensions.md)：五维审查细则
- [references/review-report-template.md](references/review-report-template.md)：批量报告模板

## 复用脚本

| 脚本 | 用途 | 使用阶段 |
|---|---|---|
| `${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/scripts/post_write_audit.py` | AI词/对话比/字数/乒乓句 | Step 1 自动检测 |
| `${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/scripts/plot_continuity_checker.py` | 伏笔回收/时间线 | 批量 Step 2 |
| `${CLAUDE_PLUGIN_ROOT}/skills/novel-memory/scripts/character_consistency_checker.py` | 角色OOC | 批量 Step 2 |
| `${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/scripts/audit_dashboard.py` | 跨章节聚合报告 | 批量 Step 3 |
