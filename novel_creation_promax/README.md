# novel_creation_promax（核心引擎）

> **这里不是技能目录。** 插件技能在 [`../skills/`](../skills/)；本目录是技能共享的核心库、流水线脚本和参考文档。

## 目录

| 路径 | 内容 |
|---|---|
| [`core/`](core/) | 共享 Python 库：passport、commit、workflow、review、integrity、knowledge_routes、dashboard、roots 等 |
| [`scripts/`](scripts/) | 写章流水线脚本：`write_pipeline.py`、`pre_write_check.py`、`writing_gate.py`、`post_write_audit.py`、`story_truth_manager.py`、`project_bootstrap_pipeline.py` 等 |
| [`references/`](references/) | 技能共享参考：`orchestrator.md`、`写作速查卡.md`、`review-result-schema.md`、`chapter_constraint_template.md` 等 |
| [`docs/`](docs/) | 架构与产物文档：`ARCHITECTURE.md`、`ARTIFACTS.md`、`PIPELINE.md`、`DATA_ACCESS_LEVELS.md` |
| [`assets/`](assets/) | 语料与模板：毒舌知识库、神回复示例、话废语料、`memory_structure.json` |
| `MODE_REGISTRY.md` | 18 个模式的唯一真源（编号、触发、入口、产物、门禁） |

## 修改时去哪里

| 要改什么 | 改哪里 |
|---|---|
| 技能的触发词、入口步骤 | [`../skills/<name>/SKILL.md`](../skills/) |
| 写章状态机、门禁、审计 | `scripts/` + `references/orchestrator.md` + `docs/PIPELINE.md` |
| 模式编号、路由 | `MODE_REGISTRY.md` |
| 共享工具函数 | `core/`（脚本应复用，不要重复实现） |
| 写作参考/模板 | `references/` |
| 语料库 | `assets/`（长期知识仍写入 `../knowledge_base/`） |

## 边界

- 本目录随插件分发，运行时只读；产物写 `${CLAUDE_PROJECT_DIR}`。
- `assets/` 是语料，不是知识库；知识库在 `../knowledge_base/`。
- [`agents/openai.yaml`](agents/openai.yaml) 是 Codex 的遗留清单，不属于 Claude 子代理；Claude 子代理在 [`../agents/`](../agents/)。
- 本目录不再放 `SKILL.md`；技能目录拍平后，技能统一在 `../skills/`。

## 验证

```bash
python3 -m unittest discover -s tests
python3 novel_creation_promax/scripts/skill_health_check.py
bash tools/ci.sh
```
