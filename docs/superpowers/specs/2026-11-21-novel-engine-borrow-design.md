# 借鉴 novel-engine 的补齐设计（P0/P1/P2）

- 日期：2026-11-21
- 状态：已实施，`bash tools/ci.sh` 通过（296 tests，28 evals）
- 来源：`/Users/narain/.workbuddy/skills/novel-engine` v3.0.2（MIT）

## 1. 判断

插件已通过 `knowledge_base/40_Writing/引擎方法索引.md` 吸收 novel-engine v3.0.2 的 38 份 references，知识层基本齐备。本次只补三类缺口：

- 机器可读结构：章节/场景 spec。
- 工具能力：作战表生成、章节快照备份。
- 被压缩掉的方法与治理：24 组提示词、作者声纹、AI 变现现实、知识库治理纪律。

不整体复制 38 份 references，不复制其工作空间布局和单体 skill 打包方式。

## 2. P0

### 2.1 章节 / 场景 spec

新增：

- `novel_creation_promax/references/chapter-spec-schema.md`
- `tools/chapter_spec.py`

能力：

- `scaffold` 生成模板。
- `validate` 校验：章节/标题/摘要、before/after state、场景目标与结果差距、主要场景 outside ≥3 轮、inside 非空、张力曲线升序、change 七选一。
- `to-scene-plan` 转 `tools/scene_passport.py init` 可用的场景计划。

### 2.2 作战表生成

`tools/chapter_rhythm.py` 新增 `--gen N --out 作战表.md`：

- 按 10 章循环生成事件/爽点/钩子/伏笔/字数骨架。
- 字数目标取 `core/thresholds.py` 的平台区间中点。
- 生成结果可被同一个脚本 `--table` 解析和检查。

## 3. P1

### 3.1 章节快照备份

新增：

- `novel_creation_promax/core/chapter_backup.py`
- `tools/backup.py`

快照内容：正文、`设定/`、本章 `摘要/`、`记忆/`、`novel_state.json`、本章 commit。每章默认保留最近 5 份；`--keep 0` 不清理。

`write_pipeline.py post --phase commit` 成功后自动生成快照；`--no-backup` 关闭。

### 3.2 24 组提示词库

新增 `novel_creation_promax/references/prompt-library.md`：

- 创作类 8 组、设计类 10 组、包装类 3 组、质检类 3 组。
- 五条禁忌与自检。
- 接入 `_ROUTES.json`、`_ROUTING.md`、`trigger-rules.md` 和 `novel-chapter-write`。

### 3.3 作者声纹与提示词粒度

在 `knowledge_base/40_Writing/02_节奏与结构/跨章规范与七遍改稿.md` 增加：

- 作者声纹：来自真实经历的取舍，AI 只能模仿节奏。
- 提示词粒度的两难：太粗交套路，太细交应试作文；验收交给流水线。

## 4. P2

### 4.1 AI 变现与平台治理现实

新增 `knowledge_base/60_Platform/AI变现与平台治理现实.md`：

- 纯 AI 投稿的边界、收入结构、合规路线、番茄/七猫对比、朱雀等检测环境、AI 不能取代的四件事。
- 标注数据截至 2026 年，>60 天需复核。
- 接入 `_ROUTES.json`、`_ROUTING.md`、`trigger-rules.md` 和 `novel-diagnose`。

### 4.2 知识库治理纪律

新增 `knowledge_base/KNOWLEDGE_GOVERNANCE.md`：

- 一个主题只有一个主人。
- 一个数只有一个出处。
- 脚本只检查已写下的规则。
- 按需只读优先于合并。
- 只收通用层。
- 时效数据 >60 天先核验。
- 版本与清单同步。
- 改完必须验。

并在 `knowledge_base/CLAUDE.md` 增加入口。

## 5. 验证

```bash
bash tools/ci.sh
```

结果：296 tests，28 evals，skill health 0/0，能力包 3 个 0 错误，插件体检 0 错误。

新增评测：

- `chapter-spec-schema-contract`
- `prompt-library-contract`
- `ai-reality-contract`
- `knowledge-governance-contract`

## 6. 非目标

- 不复制 novel-engine 的 38 份 references。
- 不引入 YAML 依赖；章节 spec 使用 JSON。
- 不让 spec 替代 9 问、知识包、rule_stack、审稿或 commit。
- 不把备份做成外部服务；只写工作区 `素材/备份/`。
- 不承诺 AI 变现收益，不提供绕过检测的方案。
