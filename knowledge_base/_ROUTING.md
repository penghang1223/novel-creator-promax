# 知识库路由表（单一来源）

> **作用**：所有"每章必读 / 按需读取"的入口都从这里分发。
> CLAUDE.md 和 SKILL.md 不再列具体文件清单，只指向这里。
> 机器可读唯一契约是 [`_ROUTES.json`](_ROUTES.json)；本文件是人读版说明，修改路由时两边同步。

---

## 每章必读（5 项，无论什么场景）

| # | 文件 | 用途 |
|---|---|---|
| 1 | `novel_creation_promax/references/writing_constitution.md` | 写作宪法（红线+节奏+人物原则） |
| 2 | `novel_creation_promax/references/写作速查卡.md` | 浓缩可执行规则 |
| 3 | `novel_output/{平台}/{书名}/细纲/卷X_xxx.md` | 本章对应细纲 |
| 4 | `novel_output/{平台}/{书名}/正文/第(N-1)章-xxx.md` | 上一章正文 |
| 5 | `novel_creation_promax/references/chapter_constraint_template.md` | 本章约束模板 |

---

## 按场景按需读取（由 `write_pipeline.py pre` 输出）

### 写前立项（仅长篇第 1 章）
- `knowledge_base/50_Quality/红线检查/章节前检查.md`
- `knowledge_base/50_Quality/评估系统/评分体系.md`

### 高压力 / 反派 / 暴露场景
- `knowledge_base/40_Writing/04_场景与描写/潜台词与张力技法.md`
- `knowledge_base/40_Writing/04_场景与描写/爽点设计.md`

### 对话密集（对话占比预计 ≥ 40%）
- `knowledge_base/40_Writing/03_人物与对话/对话质感完整框架.md`
- `knowledge_base/40_Writing/03_人物与对话/AI对话丰满化技法.md`
- `knowledge_base/40_Writing/03_人物与对话/乒乓球短句病治疗.md`

### 节奏 / 卡章 / strand 调度
- `knowledge_base/40_Writing/02_节奏与结构/strand节奏追踪.md`
- `knowledge_base/40_Writing/02_节奏与结构/每章节奏公式与卡章技巧.md`

### 题材特化（按本书题材）
- `knowledge_base/10_WorldBuilding/题材知识库/{题材}.md`

### 风格漂移检测后
- `knowledge_base/40_Writing/05_降AI痕迹/降低AI痕迹.md`
- `knowledge_base/40_Writing/05_降AI痕迹/风格硬约束.md`

### 开篇章节（前 5 章）
- `knowledge_base/40_Writing/01_开篇技巧/黄金三章技巧.md`
- `knowledge_base/40_Writing/01_开篇技巧/开头钩子库.md`

### 短篇模式
- `knowledge_base/40_Writing/07_短篇与模板/短篇创作模板.md`
- `novel_creation_promax/references/short-story-workflow.md`（任务边界、写前检查、整篇验收）

### 亲密 / 感情线
- `knowledge_base/40_Writing/04_场景与描写/亲密场景写作指南.md`（注意：`亲密场景写作.md` 已 deprecated）

### 提示词 / 场景指令
- `novel_creation_promax/references/prompt-library.md`（24 组创作/设计/包装/质检指令）

### 动漫分镜 / 视觉提示词
- `knowledge_base/动漫分镜生成.md`
- 输出写到工作区 `素材/分镜/{书名}/`；不改正文。

### 短剧改编 / 分集设计
- `knowledge_base/40_Writing/07_短篇与模板/短剧改编10维.md`
- `knowledge_base/40_Writing/07_短篇与模板/短剧改编指南.md`
- `novel_creation_promax/references/docs/short-drama-adaptation.md`
- 输出写到工作区 `素材/短剧/{书名}/`；不改正文。

### 作家风格借鉴（用户明确要求时）
- `knowledge_base/40_Writing/风格指南/写作风格技能合集/{作家}-writing-style/SKILL.md`
- 可用作家：bing-lin / chen-dong / er-gen / feng-huo / fo-qian / gun-kai / hu-wei / hu-zi / mai-bao / mao-ni / peng-pai 等

## 引擎方法（按需读取）

> 来自 novel-engine 的提炼，统一索引入口：`knowledge_base/40_Writing/引擎方法索引.md`。
> 数字以 `_PROFILES.json` 与 `core/thresholds.py` 为准，不照抄外部口径。

| 场景 | 读什么 |
|---|---|
| 立项 / 题材能不能写 | `50_Quality/评估系统/15维爆款命中率.md` |
| 开篇验收 / 前三章没人看 | `40_Writing/01_开篇技巧/开篇100分卡.md` |
| 写后机检 / 投稿前深度审稿 | `50_Quality/量化门禁/10步量化门禁.md` · `50_Quality/评估系统/16维深度审稿.md` |
| 长篇连载 / 每 5-10 章复盘 | `30_Plot/六台账与20条毒点.md` · `40_Writing/02_节奏与结构/跨章规范与七遍改稿.md` · `40_Writing/06_质量校验/章节节奏R1-R8.md` · `40_Writing/06_质量校验/长篇实战教训.md` |
| AI 味重 / 过检测 | `40_Writing/05_降AI痕迹/朱雀祛AI味五维.md` · `40_Writing/05_降AI痕迹/AI禁用词与句式表.md` |
| 上线后数据差 / 断流 / 切书 / 换平台 | `60_Platform/数据诊断与救盘.md` · `60_Platform/平台机制与换挡.md` |
| AI 变现 / 纯 AI 投稿 / 朱雀环境 | `60_Platform/AI变现与平台治理现实.md` |
| 人物声线 / 结构 / 句式 / 短剧 | `20_Characters/人物声线与弧线卡.md` · `30_Plot/叙事结构与场景节点.md` · `40_Writing/03_人物与对话/句式骨架与提示词库.md` · `40_Writing/07_短篇与模板/短剧改编10维.md` |
| 插章 / 重编号 | `40_Writing/06_质量校验/插章与重编号.md` |

自动选择规则：`engine_opening`（前 5 章）、`engine_continuity`（每 5 章）、`engine_quality` / `engine_deai` / `engine_craft` / `engine_insert`（标题关键词命中）。`engine_project` 和 `engine_ops` 为手动/命令入口，不进入每章 knowledge pack。

---

## 写后审计（强制硬门禁）

写完每章必跑，不跑则禁止写下一章：

```bash
python novel_creation_promax/scripts/write_pipeline.py post \
  --novel-dir "novel_output/{平台}/{书名}" \
  --chapter N --title "第N章 xxx"
```

产物：`素材/audit_chN.json` + `摘要/chapter_NNN_passport.json`。

下一章 `pre` 阶段优先检查上一章 passport 的 `pipeline.post_write_audit=pass`，兼容读取 `novel_state.json.last_audit_chapter`；仅有 audit 文件存在不再放行。

---

## 评估系统（按阶段调用，不要全部都跑）

| 阶段 | 调用 |
|---|---|
| 创意立项 | `50_Quality/评估系统/创意评估.md` |
| 设定完成 | `50_Quality/评估系统/设定评估.md` |
| 大纲完成 | `50_Quality/评估系统/大纲评估.md` |
| 卷结构完成 | `50_Quality/评估系统/结构评估.md` |
| 每章写后 | `50_Quality/评估系统/内容评估.md`（已被 `post_write_audit.py` 实现） |
| 每 5-10 章复盘 | `50_Quality/六编辑审稿系统.md` |
| 上线后 | `50_Quality/发布后复盘/发布后复盘指南.md` |

`50_Quality/质量门.md` / `质量保证指南.md` / `闭环质量控制.md` 已 deprecated，见 `_LEGACY_INDEX.md`。

---

## 80_Projects 项目内必读

每本小说写章前必读对应项目目录：

- `knowledge_base/80_Projects/{编号_书名}/_config.md`
- `knowledge_base/80_Projects/{编号_书名}/项目索引.md`
- `knowledge_base/80_Projects/{编号_书名}/伏笔追踪/总表.md`
- `knowledge_base/80_Projects/{编号_书名}/角色状态/{出场角色}.md`
- `knowledge_base/80_Projects/{编号_书名}/剧情节点/主线.md`

项目编号历史漂移由 `knowledge_base/80_Projects/_PROJECT_ALIASES.json` 统一解释；运行时以 `novel_output` 的 canonical id 为准，不直接重命名知识库历史目录。

---

## 共享记忆（双端实例共用，启动时读取）

- `MEMORY.md`
- `.claude/memory/decisions/preferences.md`
- `.claude/memory/active_novels/progress.md`
- `.claude/memory/feedback/corrections.md`
- `.claude/memory/feedback/no-mer-names.md`
- `.claude/memory/feedback/ai_blacklist.md`

---

## 维护规则

- **修改路由 = 修改本文件**，不要在 CLAUDE.md / SKILL.md 里复制具体文件清单
- 新增知识文件 → 同步加到本路由表对应分类
- 文件 deprecated → 同步更新本路由 + `_LEGACY_INDEX.md`
- 每月一次 `tools/file_reference_counter.py --top 30` 检查孤儿文件
