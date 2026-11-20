---
name: novel-publish
description: 平台格式转换、待发章节同步、草稿上传和明确授权后的番茄/起点/知乎/七猫发布。用户说“同步到平台”“存草稿”“发布第N章”“番茄格式”时使用。
---

# 小说发布与同步

读取并严格执行：

1. `${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/publishing/SKILL.md`
2. `${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/MODE_REGISTRY.md` 的 `platform-output` 模式

## 边界

- 发布前核验 passport、审计状态、字数和用户授权范围。
- 把章节质量不达标、账号未登录、平台规则变化如实报告给用户。
- 登录态、cookies 和平台配置只存工作区，禁止写入插件目录。
- 未经用户明确授权，不执行外部发布；本地同步与草稿上传要区分清楚。
