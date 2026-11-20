# Changelog

## 0.3.0

- 新增项目级工作流：research → idea → init → write → publish。
- 新增 `tools/workflow.py` 阶段状态与门禁工具。
- 新增 `novel-workflow` 技能与 `/workflow` 命令。
- 新增 `docs/WORKFLOW.md`：阶段表、状态文件、门禁与跳过规则。
- `MODE_REGISTRY` 增加模式 16（workflow）。
- 调研/创意/立项/写章/发布命令接入阶段记录。

## 0.2.1

- 统一创意评分规则：总分 ≥75 且无低于 8 的维度才直接推荐立项；有短板时提示先补强。
- 补充评分工具与技能文案的一致性测试。

## 0.2.0

- 新增 `novel-market-research` 技能与 `/research` 命令：平台热门方向、榜单题材、可执行选题。
- 新增 `novel-idea` 技能与 `/idea` 命令：创意卡、差异化检查、五维评分。
- 新增 `tools/idea_score.py` 加权评分工具。
- 新增市场调研与创意卡模板。
- `MODE_REGISTRY` 增加模式 14（market-research）和 15（idea-generation）。
- 知识路由健康检查支持 `skills/`、`commands/`、`hooks/`、`tools/` 路径。

## 0.1.0

首个插件化版本。

- 新增 `plugin.json` 与本地 marketplace 清单。
- 新增 `skills/` 路由与能力适配层。
- 新增 10 个斜杠命令：init / plan / outline / write / review / polish / memory / publish / audit / doctor。
- 新增 `SessionStart` 与 `PreToolUse` hooks。
- 新增双根路径解析：插件资产只读，用户作品写入工作区。
- 新增 `tools/plugin_doctor.py` 插件体检。
- 新增跨产物一致性校验与写章流水线回归测试。
- 知识库裁剪为插件内置核心版；个人项目数据不随包分发。
