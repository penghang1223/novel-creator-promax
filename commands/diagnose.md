---
description: 上线后数据诊断、断流急救、书测与切书决策
argument-hint: "[平台] [数据文件]"
---

读取并执行 `${CLAUDE_PLUGIN_ROOT}/skills/novel-diagnose/SKILL.md`。

先要齐 11 项数据，再运行：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/data_diagnosis.py" --input "{数据文件}" --json
```

输出阶段、最严重指标和七天动作。不改正文，不承诺流量或收益。
