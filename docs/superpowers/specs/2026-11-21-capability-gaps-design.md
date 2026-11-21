# 能力缺口补齐设计

- 日期：2026-11-21
- 状态：已实施，`bash tools/ci.sh` 通过（285 tests）
- 范围：番茄发布器、拆文续写、动漫分镜/短剧改编

## 1. 背景

能力审计发现三个缺口：

1. `auto_publish/fanqie_auto_publish/` 只有 README，没有发布器；起点/知乎/七猫已有 `publish.py`。
2. “续写他人作品”只有 `style_dna_extractor.py` 和 `deconstruct_novel.py`，没有从拆文到可续写项目的端到端流程。
3. 动漫分镜、短剧改编只有知识库文档，没有技能和命令入口。

## 2. 番茄发布器

### 决定

不把第三方 Playwright 引擎复制进 GPL 仓库。新增**桥接层**：

- `auto_publish/fanqie_auto_publish/publish.py`
- `auto_publish/fanqie_auto_publish/login.py`
- `auto_publish/fanqie_auto_publish/_bridge.py`

### 引擎解析

1. `NOVEL_FANQIE_PUBLISHER` 指向 `publish.py` 或其目录
2. `~/fanqie_auto_publish/`
3. `{workspace}/.novel_publish/fanqie/engine/`
4. `auto_publish/fanqie_auto_publish/engine/`

### 运行目录

引擎以 `{workspace}/.novel_publish/fanqie/` 为 cwd 运行：

```text
{workspace}/.novel_publish/fanqie/
├── state.json
├── chapters/
├── short_chapters/
├── uploaded/
└── short_uploaded/
```

首次运行会把引擎目录的 `state.json` 复制过来。`scripts/sync_to_fanqie.py` 同步目标也改为该目录，不再写插件根。

### 命令

```bash
python3 auto_publish/fanqie_auto_publish/publish.py --check
python3 auto_publish/fanqie_auto_publish/publish.py --book "书名" --count 3 --draft
python3 auto_publish/fanqie_auto_publish/login.py
```

## 3. 拆文续写

### 入口

- `novel_creation_promax/scripts/continuation_import.py`
- `skills/novel-continuation/SKILL.md`
- `commands/continue.md`
- `project_bootstrap_pipeline.py continuation-gate`

### 流程

```text
拆文 → 初始化项目 → 导入真相文件 → 生成设定/结构/细纲/报告
     → 用户审查 → continuation-gate --approve → 写续写章
```

### 关键约束

- 拆文记录 `source=deconstruction_import`，表示推断，不是作者确认。
- 导入后 `can_write_chapter=false`；只有 `continuation-gate --approve` 能解锁。
- 门禁写 `bootstrap_status=continuation_import`，与长篇 `seal` 区分，不声称立项清单通过。
- 真相文件校验在 `import_mode=continuation` 下允许部分类别为空，但已有记录仍无占位词、字段完整。
- 章节号从原文最后一章 + 1 开始。
- 单文件多章文本会自动按“第N章”拆分。

### 新增/修改

| 文件 | 作用 |
|---|---|
| `continuation_import.py` | 拆文、建项目、导入、报告 |
| `story_truth_manager.py` | `import-deconstruction`、`validate --continuation` |
| `project_bootstrap_pipeline.py` | `continuation-gate` |
| `deconstruct_novel.py` | 单文件多章拆分 |
| `skills/novel-continuation/` | 技能边界与流程 |
| `commands/continue.md` | 命令入口 |

## 4. 动漫分镜 / 短剧改编技能化

### 新增

| 文件 | 输出 |
|---|---|
| `skills/anime-storyboard/SKILL.md` | 角色形象、角色/场景提示词、Sora JSON、分镜表 |
| `skills/short-drama-adaptation/SKILL.md` | 10 维评估、分集大纲、钩子表、风险清单 |
| `commands/storyboard.md` | `/novel-creator-pro:storyboard` |
| `commands/short-drama.md` | `/novel-creator-pro:short-drama` |

### 路由与模式

- `MODE_REGISTRY.md` 新增模式 18（anime-storyboard）、19（short-drama-adaptation）。
- `_ROUTES.json` 新增 `storyboard`、`short_drama` 路由。
- `_ROUTING.md`、`trigger-rules.md` 同步人读入口。
- `skill_health_check.py` 模式范围改为 0-19，并校验两个新技能。

### 边界

- 两者都只读正文与设定，不改正文。
- 分镜产物写 `素材/分镜/{书名}/`；短剧产物写 `素材/短剧/{书名}/`。
- 分镜不复制受版权保护的角色设计；短剧不承诺售出或收益。

## 5. 验证

```bash
bash tools/ci.sh
```

结果：

- 285 tests，0 失败
- skill health `errors=0 warnings=0`
- 能力包 3 个，0 错误
- `knowledge_routes_check.py`：missing=0
- 真实工作区：番茄引擎解析到 `~/fanqie_auto_publish/publish.py`，`--check` 通过；`sync_to_fanqie.py --list` 正常。

## 6. 非目标

- 不复制第三方发布引擎源码。
- 不自动延长原文或伪造作者授权。
- 不把拆文统计当作细纲或人物小传。
- 不承诺分镜/短剧可直接商用或过审。
