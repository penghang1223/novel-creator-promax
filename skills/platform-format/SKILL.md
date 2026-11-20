---
name: platform-format
description: 平台格式转换与发布前检查。用户说“番茄格式”“起点格式”“同步到平台”“存草稿”“发布第N章”时使用。按 _PROFILES.json 检查字数/标题/段落/平台规则，生成平台稿；外部发布需明确授权。
---

# 平台格式与发布前检查

## 职责

只负责**平台稿格式、字数门禁、标题格式、段落/标点规范、草稿同步和发布前检查**；不写正文、不改剧情。

默认只做本地转换和草稿；**外部发布必须得到用户明确授权**。

## 必读

1. `${CLAUDE_PLUGIN_ROOT}/knowledge_base/60_Platform/_PROFILES.json`
2. `${CLAUDE_PLUGIN_ROOT}/knowledge_base/60_Platform/平台规则.md`
3. `${CLAUDE_PLUGIN_ROOT}/knowledge_base/60_Platform/平台机制与换挡.md`
4. `${CLAUDE_PLUGIN_ROOT}/skills/novel-publish/SKILL.md`
5. `${CLAUDE_PLUGIN_ROOT}/skills/novel-publish/SKILL.md`

## 工具

```bash
# 发布前平台门禁（字数、格式、平台规则）
python3 "${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/scripts/writing_gate.py" \
  --chapter "{章节文件}" --novel-dir "{小说目录}"

# 番茄发布器（仅草稿；外部发布需授权）
cd "${CLAUDE_PLUGIN_ROOT}/auto_publish/fanqie_auto_publish"
python3 publish.py --book "{书名}" --count N --draft
```

其他平台发布器：`qidian_auto_publish`、`zhihu_auto_publish`、`qimao_auto_publish`。

## 工作流

1. **确认平台**：番茄/起点/知乎/七猫；未定先问，不默认番茄。
2. **读平台档案**：字数区间、推荐区间、内容模式。
3. **本地检查**：
   - 单章字数是否在平台区间。
   - 标题格式是否符合平台习惯。
   - 段落长度、空行、标点是否统一。
   - 是否有平台敏感词/格式禁忌。
4. **生成平台稿**：写入工作区 `novel_output/{平台}/{书名}/发布/` 或 `素材/平台稿/`；原稿不动。
5. **草稿同步**：明确说“存草稿”，不上传公开章节。
6. **外部发布**：用户明确说“发布”后，再执行发布器，并报告实际结果。
7. **记录**：在 `novel_state.json.publish_state` 记录平台、章节、状态、时间、失败原因。

## 平台差异速查

| 项 | 番茄 | 起点 | 知乎 | 七猫 |
|---|---|---|---|---|
| 字数 | 以 `_PROFILES.json` 为准 | 以 `_PROFILES.json` 为准 | 以 `_PROFILES.json` 为准 | 以 `_PROFILES.json` 为准 |
| 节奏 | 快，前 300 字出异常 | 可稍缓，重升级体系 | 单篇闭环、强反转 | 同番茄 |
| 对话占比 | 偏高 | 中 | 中高 | 偏高 |
| 章末 | 强钩子 | 可稍缓 | 反转/余味 | 强钩子 |
| 发布方式 | 草稿/公开 | 草稿/公开 | 盐选投稿 | 草稿/公开 |

## 输出格式

```text
平台稿检查
- 平台：{平台}
- 字数：{实际} / 区间 {min}-{max}
- 标题：{通过/需改}
- 段落/标点：{通过/需改}
- 敏感词：{命中项}
- 平台稿：{路径}
- 发布状态：{未同步/已存草稿/已发布/失败}
```

## 硬规则

- 未经用户明确授权，不执行公开章节发布。
- 不覆盖原稿；平台稿另存。
- 不伪造发布成功；以发布器输出和平台后台为准。
- 平台规则会变；引用规则时标注来源和日期。
- 登录态、cookies 只存工作区，禁止写入插件目录。
- 字数以 `_PROFILES.json` 为准，不另立一套数字。

## 边界

- 不写正文、不改剧情、不改大纲。
- 不替代 `post_write_audit.py` 和 `reviewer`。
- 平台稿格式变化不影响项目正文；正文仍是唯一真源。
