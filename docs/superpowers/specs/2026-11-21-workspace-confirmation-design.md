# 工作区输出位置确认设计

- 日期：2026-11-21
- 状态：已实施（2026-11-21），`bash tools/ci.sh` 通过
- 范围：`novel-creator-pro` 插件的工作区确认协议

## 1. 背景

插件的所有产物都写入 `workspace_root()`：

1. `NOVEL_WORKSPACE_ROOT`
2. `CLAUDE_PROJECT_DIR`
3. 插件根（兜底）

用户在哪个目录启动 Claude Code，`novel_output/`、`素材/`、`创意/`、`MEMORY.md`、`.claude/memory/`、`knowledge_base/80_Projects/` 就静默落在哪里。实际已经发生过一次：在插件源码仓库里启动，产物写进了插件仓库。

根因不是脚本硬编码当前目录，而是“工作区”只有解析规则、没有**确认状态**。“从这里启动”不等于“同意把小说写在这里”。

## 2. 目标

- 首次在某个目录开始创作时，由 Claude 在对话中展示绝对路径，等用户确认后再写文件。
- 确认一次后，在同一工作区不再重复询问。
- 已有书籍的存量工作区自动视为已确认，升级不打断连载。
- 插件资产根永远不能作为写作工作区。

## 3. 非目标

- 不引入全局配置（如 `~/.config/novel-creator-pro/`）。
- 不改变 `workspace_root()` 的解析优先级。
- 不做每本书确认。
- 不在脚本里使用 `input()` 交互；确认由 Claude 在对话中完成。
- 不改变正文、passport、commit、`novel_state.json` 的写入规则。

## 4. 术语

| 术语 | 含义 |
|---|---|
| 工作区根 | `workspace_root()` 解析出的绝对路径 |
| 确认标记 | 工作区根下的 `.novel-workspace.json` |
| 已确认 | 标记存在、可解析、路径与当前工作区根一致 |
| 存量工作区 | 存在 `novel_output/{平台}/{书名}/novel_state.json` 但无有效标记 |

## 5. 标记文件契约

路径：`${workspace_root}/.novel-workspace.json`

```json
{
  "schema_version": "1.0",
  "confirmed": true,
  "workspace": "/abs/path/to/workspace",
  "confirmed_at": "2026-11-21T16:50:00",
  "confirmed_by": "user"
}
```

字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `schema_version` | string | 固定 `"1.0"` |
| `confirmed` | bool | 必须为 `true` 才算确认 |
| `workspace` | string | 确认时的绝对路径 |
| `confirmed_at` | string | ISO 时间，秒级 |
| `confirmed_by` | string | `"user"` / `"legacy"` / `"cli"` |

写入采用“临时文件 + `os.replace`”，避免半截 JSON。

`.gitignore` 需要忽略该文件：它是本地运行状态，不跨机器共享。

## 6. 判定算法

```text
status(workspace):
  1. dangerous = ""
     - workspace == plugin_root() → dangerous="plugin_root"，confirmed=false
     - workspace == "/" → dangerous="root"，confirmed=false
     - workspace == Path.home() → dangerous="home"（不阻止，仅警告）
  2. 若 dangerous 为 "plugin_root" 或 "root"：直接返回未确认
  3. 读取 .novel-workspace.json
     - 不存在 / 解析失败 / confirmed != true → 未确认，reason="missing" 或 "invalid"
     - workspace 字段 != 当前绝对根 → 未确认，reason="path_mismatch"
     - 否则 → 已确认
  4. 若未确认，统计 novel_output/*/*/novel_state.json
     - 数量 > 0 → legacy_books=N，可自动确认
     - 数量 = 0 → 必须人工确认
```

路径比较统一使用 `Path.resolve()`，避免软链接和相对路径误判。

## 7. 确认流程（用户可见）

写入入口执行前：

1. Claude 运行 `tools/workspace.py status --json`。
2. 若 `confirmed=true`，继续。
3. 若 `legacy_books>0`，Claude 运行 `tools/workspace.py confirm --legacy` 自动补标记，继续。
4. 若未确认且没有存量书：
   - Claude 展示：
     - 工作区根绝对路径
     - 将创建/写入的路径清单
     - 当前检测到的书籍数量（通常为 0）
   - 询问用户：确认这里 / 换一个目录。
   - 用户确认后运行 `tools/workspace.py confirm`。
   - 用户要求换目录：提示在目标目录重新打开 Claude Code，或设置 `NOVEL_WORKSPACE_ROOT`，然后重新确认；本次不写任何文件。
5. 若 `dangerous="plugin_root"`：直接停止，提示“插件资产根不能作为写作工作区”，不提供确认选项。

将要展示的写入清单固定为：

```text
novel_output/{平台}/{书名}/
素材/调研/
创意/
创意库/
MEMORY.md
.claude/memory/
knowledge_base/80_Projects/
```

只有实际入口会创建的项才需要展示；`init` 展示全部，`workflow start` 展示 `novel_output/` 与 `_workspace/`。

## 8. 门禁接入点

新增模块：`novel_creation_promax/core/workspace_confirmation.py`

导出：

| 函数 | 用途 |
|---|---|
| `status(workspace) -> dict` | 只读判定，返回 confirmed/reason/legacy_books/dangerous |
| `confirm(workspace, *, by="user") -> dict` | 写标记；插件根拒绝 |
| `forget(workspace) -> bool` | 删除标记 |
| `require_confirmed(workspace, *, allow_legacy=True) -> dict` | 未确认时抛出带修复指令的异常；存量自动补标记 |

接入：

| 入口 | 行为 |
|---|---|
| `project_bootstrap_pipeline.py init` | 调用 `require_confirmed`；新增 `--confirm-workspace` 供脚本/测试显式确认 |
| `project_bootstrap_pipeline.py check/seal` | 调用 `require_confirmed`；存量书自动补标记 |
| `workflow.py start` | 调用 `require_confirmed`；新增 `--confirm-workspace` |
| `write_pipeline.py pre/post/all/fix/act-summary` | 调用 `require_confirmed`；已有书属于存量，自动补标记 |
| `dashboard.py` / `verify_project_integrity.py` / `plugin_doctor.py` | 只读，不设门禁 |

`research` 和 `idea` 在进入脚本前就会写文件，因此由 `commands/research.md`、`commands/idea.md`、`skills/novel-market-research/`、`skills/novel-idea/` 先执行 `workspace.py status` 并等待确认。

`--confirm-workspace` 的语义是“调用方已完成确认并授权”，会写 `confirmed_by="cli"` 的标记后继续；Claude 只应在用户明确同意后传入。

## 9. 存量兼容

- 存量工作区首次被写入入口触达时，自动写 `confirmed_by="legacy"` 的标记，并打印一行：
  `[OK] 已为存量工作区补写确认标记`
- 只读命令（status、dashboard、verify）不补标记，避免读操作产生副作用。
- 工作区被移动后，标记中的绝对路径不匹配，重新进入人工确认流程。

## 10. 危险根保护

| 根 | 行为 |
|---|---|
| `plugin_root()` | 永久拒绝，即使有标记 |
| 用户 home | 允许确认，但展示警告：“工作区是家目录，产物会散落在 home 下” |
| `/` | 永久拒绝 |

## 11. CLI 契约

`tools/workspace.py`：

```bash
workspace.py status [--json]
workspace.py confirm [--legacy] [--json]
workspace.py forget [--json]
```

退出码：

| 场景 | 退出码 |
|---|---|
| status 正常输出 | 0 |
| confirm 成功 | 0 |
| confirm 命中插件根 / `/` | 2 |
| forget 成功或本就不存在 | 0 |
| JSON 输出始终为单对象 | 0 |

`status --json` 输出示例：

```json
{
  "workspace": "/Users/.../novel-workspace",
  "confirmed": false,
  "reason": "missing",
  "legacy_books": 2,
  "dangerous": "",
  "marker": "/Users/.../novel-workspace/.novel-workspace.json"
}
```

## 12. Hook 输出

`hooks/session_start.py` 增加一行，保持只读：

| 状态 | 输出 |
|---|---|
| 已确认 | `工作区: 已确认 /path` |
| 存量未确认 | `工作区: 已识别 N 本存量书，将在下次写入时补确认` |
| 空目录未确认 | `工作区: 未确认 /path — 首次创作前需确认产物保存位置` |
| 插件根 | `工作区: 插件资产根，不能写入创作产物` |

## 13. Skill / Command / 文档改动

| 文件 | 改动 |
|---|---|
| `commands/research.md`、`idea.md`、`init.md`、`workflow.md`、`write.md` | 写入前确认工作区 |
| `skills/novel-market-research/SKILL.md`、`novel-idea/SKILL.md` | 研究/创意阶段先确认 |
| `skills/novel-project-planning/SKILL.md` | 固化立项确认流程 |
| `skills/novel-workflow/SKILL.md` | 固化启动确认流程 |
| `skills/novel-chapter-write/SKILL.md` | 首次写入前检查 |
| `docs/WORKFLOW.md` | 增加“工作区确认”章节 |
| `docs/COMMANDS.md` | 增加 `workspace.py` 条目 |
| `docs/MODE_REGISTRY.md` | 若技能描述变化，同步登记 |
| `novel_creation_promax/scripts/skill_health_check.py` | 若技能清单变化，同步 |

## 14. 错误处理

| 情况 | 处理 |
|---|---|
| 标记 JSON 损坏 | 视为未确认，`reason="invalid"`，不自动删除 |
| 标记路径不匹配 | 视为未确认，`reason="path_mismatch"` |
| 写标记失败（只读文件系统） | 抛出异常，阻止写入，提示检查目录权限 |
| 并发调用 | `os.replace` 保证最终一致；后写覆盖前写 |
| `status` 遇到不存在的目录 | `legacy_books=0`，仍可展示路径 |

## 15. 测试计划

新增 `tests/test_workspace_confirmation.py`：

1. 空目录无标记 → `confirmed=false`，`reason=missing`
2. 有效标记且路径一致 → `confirmed=true`
3. 标记路径不一致 → `confirmed=false`，`reason=path_mismatch`
4. 标记 JSON 损坏 → `confirmed=false`，`reason=invalid`
5. 存量书存在但无标记 → `require_confirmed` 补标记，`confirmed_by=legacy`
6. 插件根 → `dangerous=plugin_root`，`confirm` 退出码 2
7. `workflow.py start` 在未确认空目录 → 非零退出
8. `workflow.py start --confirm-workspace` → 成功并写标记
9. `project_bootstrap_pipeline.py init` 未确认 → 非零退出；确认后成功
10. `workspace.py status/confirm/forget` JSON 契约
11. `session_start.py` 四种状态的输出行

更新 `tests/test_plugin_hooks.py` 覆盖 Hook 新增行。

验证命令：

```bash
bash tools/ci.sh
```

## 16. 验收标准

- 在空目录运行 `/novel-creator-pro:init`，Claude 必须先展示绝对路径并等待确认，确认前不产生任何文件。
- 在已有 `novel-workspace` 运行写章命令，不出现额外确认。
- 在插件源码根运行任何写入入口，均被拒绝。
- 移动工作区后，首次写入会重新要求确认。
- `bash tools/ci.sh` 全绿。

## 17. 风险与取舍

| 风险 | 缓解 |
|---|---|
| 存量自动确认被滥用 | 只认 `novel_state.json` 这一明确证据；空目录仍强制确认 |
| 标记文件泄漏到版本库 | 加入 `.gitignore` |
| 用户确认路径后又手动改目录 | 路径不匹配会重新确认 |
| `--confirm-workspace` 被跳过用户确认 | 仅文档化的脚本/测试入口；Skill 明确要求先问用户 |

## 18. 发布与迁移

1. 实现并通过 `bash tools/ci.sh`（已完成：275 tests，errors=0）。
2. 在 `novel-workspace` 首次运行 `workspace.py status`，应识别 2 本存量书。
3. 首次写章时自动补标记，或手动运行 `workspace.py confirm --legacy`。
4. 插件根现在没有 `novel_output/`，应显示“未确认/插件资产根”状态。
5. 更新 `docs/COMMANDS.md` 与 `docs/WORKFLOW.md` 后一并提交。
