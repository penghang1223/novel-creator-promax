---
name: novel-publish
description: 平台格式转换、待发章节同步、草稿上传和明确授权后的番茄/起点/知乎/七猫发布。用户说“同步到平台”“存草稿”“发布第N章”“番茄格式”时使用。
---

# 小说发布与同步

## 边界

拥有平台输出和发布状态；不修改故事内容，不替代写后审计，也不把“同步文件”误当成“已公开发布”。

| 操作 | 外部影响 | 最低条件 |
|---|---|---|
| 格式转换/本地同步 | 仅本地发布目录 | 指定书名与平台 |
| 平台草稿 | 写入平台草稿 | 已登录、章节范围明确、质量已核验 |
| 直接发布 | 公开或提交到平台 | 用户明确指定平台、书名、章节数量和发布意图 |

## 发布器位置

发布器入口随插件分发，执行时使用绝对路径，不要依赖当前目录：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/auto_publish/fanqie_auto_publish/publish.py" \
  --book "书名" --count N --draft
```

番茄入口是**桥接层**：它从 `NOVEL_FANQIE_PUBLISHER` 或 `~/fanqie_auto_publish` 解析外部 Playwright 引擎，并以工作区 `${CLAUDE_PROJECT_DIR}/.novel_publish/fanqie/` 为运行目录。登录态、章节草稿和归档都留在工作区，不写插件目录。

章节稿从 `${CLAUDE_PROJECT_DIR}/novel_output/{平台}/{书名}/正文/` 读取，经 `scripts/sync_to_fanqie.py` 同步到 `${CLAUDE_PROJECT_DIR}/.novel_publish/fanqie/chapters/`。

## 发布前格式检查

平台稿格式、字数门禁、标题格式与草稿同步使用 `platform-format` 技能；它按 `knowledge_base/60_Platform/_PROFILES.json` 校验，不绕过本技能的发布授权边界。

## 执行

1. 读取 `knowledge_base/60_Platform/` 的目标平台规则，并确认书名、章节范围、目标操作；信息不足时只做只读预检。
2. 对待发章节检查 passport 的审计与 commit；缺失、阻塞或正文已在提交后改动时，回到 `write_pipeline.py post`，不得同步或发布。
3. 番茄入口为 `auto_publish/fanqie_auto_publish/publish.py`（桥接外部引擎）。先运行 `publish.py --check` 确认引擎和 Playwright；引擎缺失或登录态未建立时只做本地格式转换，不调用浏览器发布。同步后核验 passport `publish.status` 和 `novel_state.json.publish_state`。
4. 对起点、知乎盐选、七猫，先将平台稿置入各发布器的章节目录，再从对应 `auto_publish/*_auto_publish/` 目录执行 `publish.py --book "{书名}" --count N --draft`。只有用户明确要求直接发布时才去掉 `--draft`。
5. 发布后用平台后台或脚本输出核验结果，并将失败章节保留为待发，不得标记为成功。

## 禁止事项

- 不将未审计或未提交的章节发布。
- 不擅自扩大章节数量、平台范围或草稿/直发模式。
- 不为“只是格式转换”运行浏览器发布器。
- 登录态、cookies 和平台配置只存工作区，禁止写入插件目录。
- 未经用户明确授权，不执行外部发布；本地同步与草稿上传要区分清楚。
