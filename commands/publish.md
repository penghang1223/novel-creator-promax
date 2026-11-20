---
description: 同步或发布章节到指定平台
argument-hint: "[平台] [书名] [第N章] [--short]"
---

读取并执行 `${CLAUDE_PLUGIN_ROOT}/skills/novel-publish/SKILL.md`。

发布前核验 passport、审计状态、字数和用户授权。登录态与平台配置只存工作区。

## 阶段记录

同步/发布完成后：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/workflow.py" --workspace "${CLAUDE_PROJECT_DIR}" \
  advance --to publish --novel-dir "${CLAUDE_PROJECT_DIR}/novel_output/{平台}/{书名}"
```
