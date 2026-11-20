---
description: 对单章或全部章节运行硬审计
argument-hint: "[书名] [第N章|all]"
---

运行：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/scripts/audit_pipeline.py" \
  --novel-dir "${CLAUDE_PROJECT_DIR}/novel_output/番茄/书名" --chapter N
```

审计报告写入工作区 `素材/`。审计失败时列出问题，不要静默跳过。
