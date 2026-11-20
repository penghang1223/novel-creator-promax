# Changelog

## 未发布

- **每书独立外层工作流**：状态从全局 `novel_output/_workspace/workflow.json` 下沉到 `novel_output/{平台}/{书名}/摘要/workflow.json`，工作区索引为 `novel_output/_workspace/workflows.json`；`workflow.py` 支持 `--novel-dir`、全局 `status` 列表和 `migrate` 旧全局状态。
- **单书看板 + 总看板**：新增 `tools/dashboard.py` 与 `core/dashboard.py`，生成 `novel_output/{平台}/{书名}/看板.md` 和 `novel_output/_workspace/看板.md`；commit、workflow advance、init 后自动刷新，`--check` 检测漂移。
- **状态契约**：`verify_project_integrity.py` 新增 `resume_point` / `state.chapters[].workflow` / `passport.workflow` 三方对账、commit 必需产物（chapter/passport/audit/truth_delta）、review 指纹与 `stale/blocked` 不得提交、`rule_stack.write_ready=false` 或 critical `assumed_facts` 与正文共存检查。`PIPELINE.md` / `ARTIFACTS.md` 明确单一写者协议。
- **能力包**：新增 `knowledge_base/packs/`（`fanqie-female-romance`、`qidian-male-fantasy`、`zhihu-short-story`）与 `tools/pack_check.py`；`knowledge_routes.py` 按 platform/genre 选择 pack，能力键可触发路由；`novel_state.json` 支持 `pack_id`。
- **证据分级**：`rule_stack` 新增 `active_rules[].evidence_level`、`assumed_facts`、`evidence_policy`；`pre_write_check.py` 与 `writing_gate.py` 阻断 critical `assumed`；context-agent 任务书要求 `confirmed` / `inferred` 标注。
- **技能目录拍平**：所有 `SKILL.md` 统一放在 `skills/<name>/`；`novel_creation_promax/` 不再嵌套子技能。memory 的脚本、参考和资产整体迁入 `skills/novel-memory/`，删除 3 个转发壳；立项、记忆、审稿、发布、知识摄入和路由技能合并为单目录。健康检查新增「`SKILL.md` 仅存在于 `skills/`」规则。
- 修复第三方首次安装无法通过 `seal` 的问题：`project_bootstrap_pipeline.py init` 现在会幂等补齐工作区 `MEMORY.md`、`.claude/memory/` 四份共享记忆，并修正 `80_Projects/_config.md` 自动生成内容中的占位词。
- 7 个辅助技能（`name-generator`、`chapter-hook`、`title-blurb`、`deai-check`、`platform-format`、`data-diagnosis`、`idea-library`）从 `.claude/skills/` 迁入 `skills/`，随插件分发；正文、立项、发布、诊断和创意技能改为显式引用它们。
- 修复源码仓库内写入守卫误判：`guard_runtime_write.py` 在 `CLAUDE_PLUGIN_ROOT == CLAUDE_PROJECT_DIR`（源码仓库）时允许编辑源码，流水线状态文件保护保持不变。
- 行为红线随插件加载：`skills/novel-creator/SKILL.md` 新增「行为红线」；SessionStart 输出指向该文件，第三方安装不再依赖仓库根 `AGENTS.md`。
- 技能单一真源：`skills/` 入口技能必须委托 `novel_creation_promax/` 核心技能，`skill_health_check.py` 新增委托校验，防止两层规则漂移。
- `MODE_REGISTRY.md` 新增 `entry_type` 列（skill/doc/kb/script）；健康检查与回归测试校验 18 个模式的入口路径真实存在。
- 知识包补齐三项召回修复：选中路由文件缺失会写入 `missing_selected` 并告警（`knowledge_gate=strict` 或 `pre --strict-knowledge` 时阻断）；`retrieval` 只检索 `20_Characters`/`30_Plot`/`40_Writing`，排除项目元数据；路由触发同时匹配标题与本章细纲场景标签。
- `knowledge_pack.json` 新增 `scene_text`、`missing_required`、`missing_selected`、`status` 字段；知识包构建逻辑下沉到 `core/knowledge_routes.build_and_save_chapter_pack`。
- 知识检索默认改为 BM25（带文档长度归一化），按选中路由目录加权；检索分两阶段，先取路由目录，再用其余技法目录补位。已列入 `selected_routes` 的文件不再重复进入 `retrieval`；结果新增 `stage=route|fallback` 标记。
- `novel_state.json` 的 `retrieval_backend` 默认改为 `bm25`，仍兼容 `lexical` / `tfidf`；`tools/knowledge_search.py --backend` 同步支持三种后端。
- 同步更新 `README.md`、`AGENTS.md` 与相关测试路径。

## 0.4.0

- 新增 3 个只读子代理：`context-agent`（五段写作任务书）、`reviewer`（五维审稿）、`data-agent`（truth delta 草案）。
- 新增 `core/review_result.py` 与 `tools/review_result.py`：审稿 JSON 契约、校验、门禁状态和 Markdown 渲染。
- 写章流水线 quality 与 commit 阶段接入结构化审稿：`blocking_count > 0` 或契约无效时阻断；commit 绑定 `chapter_NNN_review.json`。
- `tribunal` 模式要求存在结构化审稿结果。
- 写章与审稿技能改为 JSON 优先：reviewer 只返回 JSON，报告由脚本渲染。
- 审稿契约新增 `target.sha256` 正文绑定、`source_refs` 原文引用和 `stale` 状态；正文变更后旧审稿自动失效。
- 新增章节 revision 身份（`current.json` + `history/`），审稿绑定 `revision_id`；proposal 批准和 snapshot 恢复会生成新 revision。
- `source_refs` 支持字符偏移 `start`/`end` 精确匹配；审稿 JSON 读取时拒绝重复字段。
- 真相文件新增 `open_questions` 未知事实通道；`rule_stack.unknown_facts` 与 `write_ready` 接入 `pre_write_check`，critical 未知事实阻断写章。
- 审稿新增 `basis` 和 `expected_versions`：绑定 rule_stack、truth_brief、taskbook、memory_pack 与审稿流程版本；任一输入变化，旧审稿变为 `stale`。
- 真相文件新增 `reader_known` / `reveal_status` / `reveal_chapter` / `knowledge_boundary` / `secrets`；`rule_stack.truth_layers` 与 `追踪/时间线/作者真相.md`、`读者已知.md` 分离作者真相和读者已知。
- 新增 `tools/reader_truth.py`；审稿 issue 新增 `code`，reviewer 增加 `POV_LEAK` 角色知识边界检查。
- 新增 `guard-outline-before-prose` hook：首次创建正文且缺少细纲时阻断。
- 新增开篇 100 分卡、15 维命中率、章节节奏 R1-R8、AI 味评分、情绪账、战力阶梯与数据诊断工具；阈值集中到 `core/thresholds.py`。
- 新增 `novel-diagnose` 技能与 `/diagnose` 命令。
- 新增长期创意库 `tools/idea_library.py` 与工作区 `创意库/`：按创意拆分归档、内容哈希查重、稳定 ID、Markdown/JSON 索引与搜索。
- 新增 `.claude/skills/` 项目专属技能：`name-generator`、`chapter-hook`、`title-blurb`、`deai-check`、`platform-format`、`data-diagnosis`、`idea-library`。
- `skill_health_check.py` 增加子代理只读权限与审稿契约文件检查。
- 新增回归测试：审稿契约、子代理 frontmatter、流水线阻断与 commit 绑定。
- 新增行为评测：`tests/evals/` + `tools/run_skill_evals.py`，检查技能步骤顺序、禁止捷径、子代理只读权限和审稿 CLI 契约；评测器自身也有反向测试。
- 同步 `commands/write.md`、`MODE_REGISTRY.md` 与 `docs/COMMANDS.md` 到最新写章链；评测新增入口一致性用例。

## 0.3.0

- 新增项目级工作流：research → idea → init → write → publish。
- 新增 `tools/workflow.py` 阶段状态与门禁工具。
- 新增 `novel-workflow` 技能与 `/workflow` 命令。
- 新增 `docs/WORKFLOW.md`：阶段表、状态文件、门禁与跳过规则。
- `MODE_REGISTRY` 增加模式 16（workflow）。
- 调研/创意/立项/写章/发布命令接入阶段记录。

## 0.2.1

- 统一创意评分规则：总分 ≥75 且无低于 8 的维度才直接推荐立项；有短板时提示先补强。
- 补充评分工具与技能文案的一致性测试。

## 0.2.0

- 新增 `novel-market-research` 技能与 `/research` 命令：平台热门方向、榜单题材、可执行选题。
- 新增 `novel-idea` 技能与 `/idea` 命令：创意卡、差异化检查、五维评分。
- 新增 `tools/idea_score.py` 加权评分工具。
- 新增市场调研与创意卡模板。
- `MODE_REGISTRY` 增加模式 14（market-research）和 15（idea-generation）。
- 知识路由健康检查支持 `skills/`、`commands/`、`hooks/`、`tools/` 路径。

## 0.1.0

首个插件化版本。

- 新增 `plugin.json` 与本地 marketplace 清单。
- 新增 `skills/` 路由与能力适配层。
- 新增 10 个斜杠命令：init / plan / outline / write / review / polish / memory / publish / audit / doctor。
- 新增 `SessionStart` 与 `PreToolUse` hooks。
- 新增双根路径解析：插件资产只读，用户作品写入工作区。
- 新增 `tools/plugin_doctor.py` 插件体检。
- 新增跨产物一致性校验与写章流水线回归测试。
- 知识库裁剪为插件内置核心版；个人项目数据不随包分发。
