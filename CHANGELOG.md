# Changelog

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
