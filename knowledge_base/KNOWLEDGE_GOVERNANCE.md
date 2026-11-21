# 知识库治理纪律

> 适用：`knowledge_base/`、`novel_creation_promax/references/`、`skills/`、`docs/` 的新增与修改。
> 目标：防止同一件事出现两个真源、同一数字出现两个口径、同一文档被反复重抄。

## 一、一个主题只有一个主人

新增内容前先问：**这件事归谁？**

| 主题 | 主人 |
|---|---|
| 平台字数、推荐区间 | `knowledge_base/60_Platform/_PROFILES.json` |
| 量化阈值、配额 | `novel_creation_promax/core/thresholds.py` |
| 机器路由 | `knowledge_base/_ROUTES.json` |
| 人读路由 | `knowledge_base/_ROUTING.md` |
| 技能 / 模式编号 | `novel_creation_promax/MODE_REGISTRY.md` |
| 章节状态 | `摘要/chapter_NNN_passport.json` + `novel_state.json` |
| 结构化故事事实 | `设定/真相文件/*.json` |
| 写作任务书 | `摘要/chapter_NNN_taskbook.md` |
| 审稿契约 | `摘要/chapter_NNN_review.json` |
| 用户偏好 | `.claude/memory/` |
| 引擎方法映射 | `knowledge_base/40_Writing/引擎方法索引.md` |

已有主人时，**只加交叉引用，不重抄全文**。如果发现两处说法不一致，先合并到主人文件，再改引用。

## 二、一个数只有一个出处

- 字数：`_PROFILES.json` 与 `core/thresholds.py`。
- 破折号、词频、配额：`core/thresholds.py`。
- AI 词表：`knowledge_base/40_Writing/05_降AI痕迹/AI禁用词与句式表.md`。
- 平台机制与换挡：`knowledge_base/60_Platform/平台机制与换挡.md`。
- 评估维度数量：`50_Quality/评估系统/` 对应文档。

任何文档要用这些数，只能回指，**不许另写一套**。改数只改主人文件，再让引用自动生效。

## 三、脚本只检查已写下的规则

- 要加判据，先改规范文档，再改脚本。
- 不许在脚本里临时立一个新标准；脚本是规范的执行器，不是规范本身。
- 新增阈值时，同步 `core/thresholds.py`、测试和对应文档。
- 脚本失败时，先判断是稿子不达标还是规范已过期，不要为了让脚本通过而改脚本。

## 四、按需只读优先于合并

- 用途不同的文档分开放，例如祛 AI 味拆成核心、词表、模式、平台规则、场景策略。
- 只有出现“同一件事两处两个说法”时才合并。
- 合并后保留旧路径的跳转说明，避免路由断链。

## 五、只收通用层

- 不收具体作品的角色名、地名、专有符号、意象池、章节流程。
- 项目级内容写工作区 `novel_output/` 和 `knowledge_base/80_Projects/`，不写通用知识库。
- 外部资料复制进来的繁体字统一转简体；来源和许可要记录。

## 六、时效数据必须带日期

- 平台规则、榜单、收益数据、检测机制，一律标采集时点。
- 超过 **60 天**必须先核验，未核验的结论标“待验证”。
- 不把旧口径写成“当前”；不把第三方解读当官方确认。

## 七、版本与清单同步

- `plugin.json` 的版本必须与根目录 `VERSION` 一致。
- 新增/修改技能后，同步 `MODE_REGISTRY.md`、`skill_health_check.py` 和对应测试。
- 新增知识文档后，同步 `_ROUTES.json`、`_ROUTING.md`，必要时同步 `引擎方法索引.md`。
- 新增命令后，同步 `commands/`、`docs/COMMANDS.md` 和路由技能。

## 八、改完必须验

提交前至少运行：

```bash
bash tools/ci.sh
python3 novel_creation_promax/scripts/skill_health_check.py
python3 tools/knowledge_routes_check.py
python3 tools/plugin_doctor.py --plugin-only
```

- 单元测试、技能评测、技能健康检查、能力包检查、插件体检全部通过才算完成。
- 只跑部分测试不算验证；不要用“我检查过了”代替命令输出。

## 九、变更记录

- 跨章节设定变更写入 `knowledge_base/80_Projects/{项目}/变更记录.md`。
- 知识库结构调整写入本文件或 `引擎方法索引.md` 的维护段。
- 修改共享规范时，说明原设计、改动和理由；不要静默覆盖。
