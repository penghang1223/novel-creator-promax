---
name: novel-doctor
description: 检查插件安装、Python 版本、可选依赖、工作区结构和项目产物一致性。用户说“体检”“为什么跑不起来”“检查环境”“插件装好了吗”时使用。
---

# 插件与环境体检

运行：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/plugin_doctor.py"
```

体检内容：

- 插件根、工作区根、技能/命令/知识路由是否完整；
- Python 版本与可选依赖（Pillow、jieba、requests、FastAPI、Playwright）；
- 工作区是否包含 `novel_output/`、`MEMORY.md`、`.claude/memory/`；
- 当前书籍的 passport、commit、`novel_state.json` 一致性。

项目级一致性单独运行：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/verify_project_integrity.py" \
  --root "${CLAUDE_PROJECT_DIR}/novel_output"
```

体检结果只报告，不自动修改项目文件。
