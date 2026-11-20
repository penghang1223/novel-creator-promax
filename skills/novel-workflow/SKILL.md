---
name: novel-workflow
description: 查看和推进项目级工作流阶段。用户说“工作流到哪了”“下一步做什么”“继续流程”“能不能进入下一阶段”“阶段门禁”时使用。负责调研→创意→立项→写章→发布的外层导航，不替代章节内部状态机。
---

# 项目工作流

外层阶段：

```text
research → idea → init → write → publish
```

## 先看状态

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/workflow.py" --workspace "${CLAUDE_PROJECT_DIR}" status
```

- 未开始：先确认平台/题材，再 `start`。
- 有状态：报告**最后完成的阶段**、下一步和 `missing` 门禁项。

## 推进规则

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/workflow.py" --workspace "${CLAUDE_PROJECT_DIR}" \
  advance --to <stage> [--evidence PATH] [--novel-dir PATH] [--note TEXT]
```

- `research`：需要 `素材/调研/*.md`；
- `idea`：需要调研报告；
- `init`：需要创意卡 + `novel_state.workflow_gate.can_write_chapter=true`；
- `write`：需要至少一个 accepted `chapter_commit`；
- `publish`：需要 `publish_state` 里的已同步/已发布记录。

默认只能推进到下一阶段。禁止跳阶段；确需跳过时必须：

```bash
--force --reason "具体原因"
```

跳过会写入 `overrides`，不得静默绕过。

## 边界

- 不替代 `seal`、`writing_gate`、`post_write_audit` 或 `verify_project_integrity`。
- 不直接修改正文、passport 或 commit。
- 证据不足时先补齐产物，不要手改 `workflow.json`。
- `gate` 只校验，不改变状态；需要变更时用 `advance`。
