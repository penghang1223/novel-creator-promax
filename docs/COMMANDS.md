# 命令与架构速查

> **按需文档**：本文件不在会话启动时加载。需要执行具体命令或查脚本职责时再读。
> 行为规则和红线仍在根目录 [CLAUDE.md](../CLAUDE.md)。

---

## Python Dependencies

依赖按模块拆分，按需安装：

- `requirements-core.txt` — 核心依赖（Pillow 等，封面生成必需）
- `requirements-dashboard.txt` — 审计面板依赖
- `requirements-publish.txt` — 发布模块依赖（Playwright）

密钥配置文件模板（已加入 `.gitignore`，**切勿提交明文密钥**）：

- `config.toml.example` — 平台 API/登录配置模板
- `cc-connect-config.toml.example` — Claude Code 连接配置模板
- `.env.example` — 环境变量模板

**虚拟环境初始化**：

```bash
python -m venv .venv
source .venv/Scripts/activate  # Windows: .venv/Scripts/activate
pip install -r requirements-core.txt        # 核心依赖（封面生成/中文分词/HTTP）
pip install -r requirements-dashboard.txt   # Web 面板依赖（FastAPI + uvicorn）
pip install -r requirements-publish.txt     # 发布依赖（Playwright）
python -m playwright install chromium       # 首次安装浏览器
```

---

## Common Commands

All commands are run from the project root. Scripts live under `novel_creation_promax/scripts/`.

### Cover generation
```bash
python novel_creation_promax/scripts/generate_cover.py --title "书名" --author "作者名" --style auto --output novel_output/{平台}/{小说名}/cover.jpg
```

### Memory system (novel-memory)

Initialize a new novel memory directory:
```bash
python skills/novel-memory/scripts/memory_manager.py init --memory-dir novel_output/{平台}/{小说名}/memory
```

Bootstrap project memory from a JSON file:
```bash
python skills/novel-memory/scripts/memory_manager.py bootstrap-project --input project_bootstrap.json --memory-dir novel_output/{平台}/{小说名}/memory
```

Generate a pre-chapter memory pack for chapter N:
```bash
python skills/novel-memory/scripts/memory_manager.py chapter-pack --chapter N --memory-dir novel_output/{平台}/{小说名}/memory --output chapter_N_pack.json
```

Sync a chapter summary back into the memory system:
```bash
python skills/novel-memory/scripts/memory_manager.py sync-chapter --input chapter_N_summary.json --memory-dir novel_output/{平台}/{小说名}/memory
```

Generate a periodic review pack (recommended every 5–10 chapters):
```bash
python skills/novel-memory/scripts/memory_manager.py review-pack --chapter N --memory-dir novel_output/{平台}/{小说名}/memory --output review_pack.json
```

Query or inspect memory stats:
```bash
python skills/novel-memory/scripts/memory_manager.py stats --memory-dir novel_output/{平台}/{小说名}/memory
python skills/novel-memory/scripts/memory_manager.py query --type character --filter "basic_info.name=沈知言" --memory-dir novel_output/{平台}/{小说名}/memory
```

### Pre/post write quality tools

Run new-project bootstrap gate (mandatory before chapter 1 of long-form projects):
```bash
python novel_creation_promax/scripts/project_bootstrap_pipeline.py init --platform "番茄" --title "书名" --genre "题材" --premise "核心设定"
python novel_creation_promax/scripts/project_bootstrap_pipeline.py seal --novel-dir "novel_output/番茄/书名"
```

`seal` must pass and set `novel_state.json.workflow_gate.can_write_chapter=true`; otherwise `write_pipeline.py` blocks正文.

Run pre-chapter check (automated 9-question scoring):
```bash
python novel_creation_promax/scripts/pre_write_check.py --chapter chapter_N.txt --memory-dir ./my_novel
```

9 问检查同时读取 `摘要/chapter_NNN_rule_stack.json` 的 `unknown_facts`；存在 critical 未知事实时 exit 1。

Run post-chapter audit (red-line scan, style drift, OOC check):
```bash
python novel_creation_promax/scripts/post_write_audit.py --chapter chapter_N.txt --memory-dir ./my_novel
```

Launch audit dashboard (aggregated quality reports):
```bash
python novel_creation_promax/scripts/audit_dashboard.py --memory-dir ./my_novel
```

### Style and consistency tools

Extract style DNA from sample text:
```bash
python skills/novel-memory/scripts/style_dna_extractor.py --input sample.txt --output style_dna.json
```

Check style drift against a saved DNA:
```bash
python skills/novel-memory/skills/novel-memory/scripts/style_calibrator.py --input chapter.txt --style-dna style_dna.json --output report.json
```

Check character consistency (OOC risk):
```bash
python skills/novel-memory/skills/novel-memory/scripts/character_consistency_checker.py --input chapter_N.txt --characters ./my_novel/characters.json
```

Generate character names (anti-collision, anti-AI-homogenization):
```bash
python novel_creation_promax/scripts/name_generator.py --gender male --style ancient_elegant --count 5
```

Check plot continuity and foreshadowing resolution:
```bash
python novel_creation_promax/scripts/plot_continuity_checker.py --check N
python novel_creation_promax/scripts/plot_continuity_checker.py --report N --format text
```

### Physical state tracking

Extract physical state (money/location/time) from a chapter and compare with previous:
```bash
python novel_creation_promax/scripts/physical_state_tracker.py --chapter-file novel_output/番茄/小说/正文/ch001.md
python novel_creation_promax/scripts/physical_state_tracker.py --chapter-file ch002.md --prev-state ch001_state.json
python novel_creation_promax/scripts/physical_state_tracker.py --chapter-file ch001.md --output ch001_state.json
```

### Story truth management

Scaffold, validate, and compile truth files for deterministic project artifacts:
```bash
python novel_creation_promax/scripts/story_truth_manager.py scaffold --novel-dir "novel_output/番茄/书名"
python novel_creation_promax/scripts/story_truth_manager.py validate --novel-dir "novel_output/番茄/书名"
python novel_creation_promax/scripts/story_truth_manager.py compile --chapter N --novel-dir "novel_output/番茄/书名"
python novel_creation_promax/scripts/story_truth_manager.py extract-delta --chapter-file ch_N.txt --novel-dir "novel_output/番茄/书名"
```

### Skill health check

```bash
python novel_creation_promax/scripts/skill_health_check.py   # skill 自检：模式编号/引用文件/脚本路径一致性
```

### Knowledge ingestion

Ingest external content into the knowledge base:
```bash
python novel_creation_promax/scripts/ingest.py --input article.md --category "40_Writing" --title "黄金三章写法"
```

### Novel deconstruction (拆文系统)

自动分析小说文本，提取角色/剧情/世界观/风格为结构化资产：
```bash
python novel_creation_promax/scripts/deconstruct_novel.py --input "正文/" --output "拆文结果/"
python novel_creation_promax/scripts/deconstruct_novel.py --input "全文.txt" --output "拆文结果/" --skip-llm-prompts
```

产物：`characters.json`（角色+关系+对话归属）、`plot_structure.json`（章节统计+转折点）、`world_settings.json`（地点/势力/专有名词）、`style_profile.json`（风格DNA）、`analysis_report.md`（可读报告）、`llm_prompts/`（深度分析提示）。

### Publishing sync

Sync novel output to Fanqie publish directories:
```bash
python scripts/sync_to_fanqie.py                    # sync all novels
python scripts/sync_to_fanqie.py --short            # sync all short stories
python scripts/sync_to_fanqie.py "书名"             # sync specific novel
python scripts/sync_to_fanqie.py --list             # list syncable novels
```

---

## Writing pipeline

一键串起写前检查 → 写作任务书 → Pass 1/2 → 结构化审稿 → 写后审计 → 记忆同步：
```bash
# 写前阶段（生成记忆包 + 9问检查）
python novel_creation_promax/scripts/write_pipeline.py pre --novel-dir "novel_output/番茄/小说名" --chapter N --title "第N章 标题"
# 可选：知识包必读项/选中路由文件缺失时阻断（也可在 novel_state.json 设置 knowledge_gate=strict）
python novel_creation_promax/scripts/write_pipeline.py pre --novel-dir "novel_output/番茄/小说名" --chapter N --title "第N章 标题" --strict-knowledge

# 写后阶段（Gate + 审计 + 风格 + 人物 + 记忆回填；失败时自动生成修复计划）
python novel_creation_promax/scripts/write_pipeline.py post --novel-dir "novel_output/番茄/小说名" --chapter N --title "第N章 标题"

# post 单阶段断点重跑：audit/truth/quality/memory/commit
python novel_creation_promax/scripts/write_pipeline.py post --novel-dir "novel_output/番茄/小说名" --chapter N --phase audit

# 一键全跑（章节文件已存在时）
python novel_creation_promax/scripts/write_pipeline.py all --novel-dir "novel_output/番茄/小说名" --chapter N --title "第N章 标题"

# 手动生成修复计划（审计失败后分析问题并生成修复指令）
python novel_creation_promax/scripts/write_pipeline.py fix --novel-dir "novel_output/番茄/小说名" --chapter N --title "第N章 标题"

# 卷级摘要（聚合该卷所有章节摘要，更新 novel_state.json）
python novel_creation_promax/scripts/write_pipeline.py act-summary --novel-dir "novel_output/番茄/小说名" --volume 1
```

**每章链路**：`pre` → `context-agent` 任务书 → Pass 1 → `writing_gate.py` → Pass 2 → `target` 取正文哈希 → `reviewer` JSON（含 target/source_refs，`tools/review_result.py save`）→ `post`（audit/truth/quality/memory/commit）。`review.json` 的 `blocking_count > 0` 或 `stale` 会阻断 quality 与 commit。

**断点续跑**：`摘要/chapter_NNN_passport.json.workflow` 保存章节状态机，`novel_state.json.resume_point` 保存跨进程提示；优先按 `next_action` 或 `action` 重跑对应阶段。`post` 支持 `audit/truth/quality/memory/commit` 单阶段重跑。

**质量债务扫描**：`python tools/quality_debt.py --output novel_output/_workspace/reports/quality_debt.json` 汇总 override、阻塞阶段、未完成流水线、缺失 commit 和待复核真相候选。

**跨产物一致性校验**：`python tools/verify_project_integrity.py --novel-dir "novel_output/番茄/书名"` 交叉核对章节、passport、commit 与 `novel_state.json`；`--root novel_output` 扫描全库，`--strict` 把 warning 也视为失败，`--json` 输出机器可读报告。

**项目工作流与看板**：每本书的外层工作流在 `novel_output/{平台}/{书名}/摘要/workflow.json`，工作区索引在 `novel_output/_workspace/workflows.json`；`python tools/workflow.py --workspace ... status [--novel-dir ...]` 查看单书或全部。`python tools/dashboard.py --workspace ...` 生成单书 `看板.md` 和总看板 `novel_output/_workspace/看板.md`，`--check` 检测漂移。

**SQLite 读模型**：`python tools/sync_story_index.py` 同步 `novel_output/_workspace/index/story_index.sqlite3`，仅用于 Dashboard 和聚合查询；正文、真相文件、passport、summary、commit 仍是唯一真源。

**修改保护**：自动修改先使用 `python tools/revision_queue.py propose ...` 生成 proposal，人工批准后才写正文；Dashboard 直接编辑会自动创建快照并清除旧 commit。

**场景级写作**：需要细化场景时使用 `python tools/scene_passport.py` 初始化场景计划；只有显式启用场景计划的章节才要求全部场景通过后 commit。

**质量模式**：`write_pipeline.py post` 默认使用 `deterministic`；关键章节可用 `--quality-mode tribunal --quality-review-report review.json`，报告必须为 `status=pass` 才允许提交。

**知识检索**：`python tools/knowledge_search.py "关键词" --backend bm25|lexical|tfidf` 查询可重建的 `knowledge_index.sqlite3`；项目可在 `novel_state.json` 设置 `retrieval_backend`，默认 BM25，章节 `knowledge_pack` 会记录检索结果，但原始知识库文件仍是真源。

**能力包**：`python tools/pack_check.py --json` 校验 `knowledge_base/packs/*/pack.json` 的信号、能力键、路由文件与坑点库；章节 `knowledge_pack` 会记录选中的 `pack_id` 与能力键。

**张力与契约**：项目可在 `novel_state.json` 配置 `tension_contract.enabled=true`，再用 `tools/tension_curve.py` 校验章节曲线；`tools/validate_contracts.py` 校验摘要、passport 和项目状态结构。

**历史张力回填**：`python tools/backfill_tension.py --apply` 只生成 `素材/tension/` 下的启发式趋势报告，不改正文、摘要或审计状态；估算报告不能替代正式质量审查。

**门禁绕过留痕**：`--override-prev-audit` 必须同时提供 `--override-reason "原因"`，否则拒绝执行；理由会写入 `novel_state.json.override_debt`，可用 `python tools/chapter_guard.py` 与 `health_check` 追踪未偿还的门禁债务。

**路径变量替换**：`pipeline_utils.resolve_novel_path()` 支持 `{平台}`、`{书名}`、`{章节号}`、`{卷号}` 等模板变量，避免硬编码路径。

**审计失败自动修复**：`post` 阶段审计不通过时，自动生成 `素材/fix_plan_chNNN.json` + `.md`，按优先级列出 AI词/对话比/风格漂移/OOC/字数等问题及修复指令。

**阶段治理审计**：`post` 阶段审计通过后，每 20 章自动触发全量趋势分析（通过率/AI词趋势/对话比例/字数变化），生成 `素材/governance_chNNN.json` + `.md`，含滑坡预警。

**章节骨架**：`pre` 阶段自动生成 `素材/skeleton_chNNN.md`，包含细纲要点、上一章回顾、活跃角色、开篇锚点/核心冲突/结尾目标清单、记忆更新清单、写中自检清单。

---

## Audit pipeline

批量审计已写章节：
```bash
python novel_creation_promax/scripts/audit_pipeline.py --novel-dir "novel_output/番茄/小说名" --from-chapter 1 --to-chapter 10
```

---

## Project health check

```bash
python tools/health_check.py        # 全量自检 18 项：密钥正则扫描/路径漂移/引用完整性/功能编号一致性/审计覆盖率
python tools/chapter_guard.py       # 章节门禁：全库"写了没审"缺口清单
python tools/chapter_guard.py --changed-only   # pre-commit 用：暂存正文必须有审计报告
bash tools/install_hooks.sh         # 启用版本化 git hooks（core.hooksPath=.githooks）
```

> 章节门禁已挂到 `.githooks/pre-commit`：新增/修改的正文若无审计报告，提交直接被拒。
> 确属例外可用 `git commit --no-verify`（会跳过所有钩子）。

---

## Tools directory

`tools/` holds standalone utilities not tied to the novel creation workflow:

- `opening_score.py` — 开篇 100 分卡 + 12 类低留存。Usage: `python tools/opening_score.py 第1章.md --check`
- `hit_rate.py` — 15 维爆款命中率与否定决/天花板封顶。Usage: `python tools/hit_rate.py --input 立项.json`
- `chapter_rhythm.py` — 章节节奏 R1-R8。Usage: `python tools/chapter_rhythm.py --table 作战表.md --check`
- `ai_flavor_score.py` — 启发式 AI 味评分。Usage: `python tools/ai_flavor_score.py 第1章.md --check`
- `emotion_ledger.py` — 情绪账：温度档、憋屈累计、上次释放。Usage: `python tools/emotion_ledger.py sync --novel-dir "novel_output/番茄/书名"`
- `idea_library.py` — 长期创意库：`init` / `archive-idea` / `archive-research` / `search` / `list` / `rebuild-index`。Usage: `python tools/idea_library.py --workspace "$PWD" search --query "番茄 女频" --json`
- `data_diagnosis.py` — 上线后 11 项数据诊断：阶段判断、症状→病因→处方、七天动作。Usage: `python tools/data_diagnosis.py --input data.md --json`
- `reader_truth.py` — 作者真相 / 读者已知分层：`sync` 生成 `追踪/时间线/` 视图，`show` 查看某一层，`validate` 校验分层完整性。Usage: `python tools/reader_truth.py sync --novel-dir "novel_output/番茄/书名" --chapter 12`
- `run_skill_evals.py` — 行为评测：检查技能步骤顺序、禁止捷径、子代理只读权限和审稿 CLI 契约。Usage: `python tools/run_skill_evals.py --json`
- `health_check.py` — 项目健康自检（18项：全仓密钥正则扫描/路径漂移/引用完整性/功能编号一致性/审计覆盖率等）。Usage: `python tools/health_check.py`
- `chapter_guard.py` — 章节写作门禁：正文必须有审计报告；`--changed-only` 供 pre-commit 使用，`--strict --min-rate` 供 CI 使用。Usage: `python tools/chapter_guard.py --strict --min-rate 0.8`
- `verify_project_integrity.py` — 跨产物一致性校验：章节 ↔ passport ↔ commit ↔ `novel_state.json`；`--root` 扫描全库，`--strict` 把 warning 也视为失败，`--json` 输出机器可读报告。Usage: `python tools/verify_project_integrity.py --root novel_output`
- `review_result.py` — 结构化审稿契约：`init` 创建待填写模板，`target --ensure-revision` 打印正文哈希并创建 revision，`validate` 校验 JSON/目标/引文，`save` 校验并写入（`--bind-target` 为兜底），`status` 查看 blocking 与 stale，`render` 输出人读报告。Usage: `python tools/review_result.py status --novel-dir "novel_output/番茄/书名" --chapter 12 --json`
- `reconcile_novel_state.py` — 对账 `novel_state.chapters[].audit` 与磁盘真实审计报告，清除"自证式通过"；默认 dry-run。Usage: `python tools/reconcile_novel_state.py --all --apply`
- `install_hooks.sh` — 启用 `.githooks/` 下的版本化 git hooks。Usage: `bash tools/install_hooks.sh`
- `backfill_audits.py` — 批量为历史章节补跑 post_write_audit（自动跳过已有审计，支持 `--force`/`--dry-run`/`--all`）。Usage: `python tools/backfill_audits.py --novel-dir "novel_output/番茄/书名"`
- `init_kb_project.py` — 为 `knowledge_base/80_Projects/` 生成项目管理骨架（`--auto` 自动扫描补齐）。Usage: `python tools/init_kb_project.py --title "书名" --id 011`
- `build_project_registry.py` — 生成 `80_Projects/_PROJECT_REGISTRY.json`（novel_output 与 80_Projects 的映射）。Usage: `python tools/build_project_registry.py --include-short`
- `knowledge_base/80_Projects/_PROJECT_ALIASES.json` — 历史项目编号/目录别名的显式映射；注册表以当前 `novel_output` 编号为 canonical id，不自动重命名历史目录。
- `knowledge_lint.py` — 扫描 knowledge_base markdown 的 status frontmatter，输出治理报告。Usage: `python tools/knowledge_lint.py --json`
- `knowledge_routes_check.py` — 校验 `_ROUTES.json` 机器可读路由的路径有效性。Usage: `python tools/knowledge_routes_check.py`
- `knowledge_base_audit.py` — 审查知识库目录契约、生命周期边界、项目骨架和索引统计。Usage: `python tools/knowledge_base_audit.py`
- `archive_knowledge.py` — 将历史知识目录安全迁移到 `knowledge_base/90_Archive/`，默认 dry-run。Usage: `python tools/archive_knowledge.py --apply`
- `read_feishu_doc.py` — 读取飞书文档/wiki 输出 Markdown。Usage: `python tools/read_feishu_doc.py <url> --output save.md`
- `file_reference_counter.py` — 统计 markdown 文件被引用次数，识别 orphan 文件。Usage: `python tools/file_reference_counter.py --top 20`
- `align_project_id.py` — 只读检查 `novel_output/` 与 `knowledge_base/80_Projects/` 的编号/命名漂移。Usage: `python tools/align_project_id.py`
- `normalize_project_state.py` — 预览/应用 `novel_state.json` v2 迁移，应用时自动备份。Usage: `python tools/normalize_project_state.py --all --apply`
- `merge_memory_aliases.py` — 无损合并重复的 `memory` / `记忆` 目录，冲突不覆盖。Usage: `python tools/merge_memory_aliases.py --all --apply`
- `backfill_project_management.py` — 为历史项目补齐 `项目章程.md` 和 `风险登记表.md`，默认 dry-run。Usage: `python tools/backfill_project_management.py --all --apply`
- `init_kb_project.py --from-output` — 为 `novel_output` 中缺失的 80_Projects 项目生成知识库骨架，默认 dry-run。Usage: `python tools/init_kb_project.py --from-output --apply`

---

## Script layer

Python scripts provide deterministic, file-based operations：

| 分类 | 脚本 | 说明 |
| --- | --- | --- |
| **质量门禁** | `pre_write_check.py` (17KB) | 写前9问评分，≥70分才能写 |
| | `writing_gate.py` | Pass 1→Pass 2 断点门禁（字数/边界/AI词/对话比） |
| | `post_write_audit.py` (33KB) | 写后审计：AI词/对话比/字数/乒乓球句 |
| | `audit_dashboard.py` (16KB) | 跨章节聚合质量报告 |
| | `audit_pipeline.py` | 批量审计已写章节 |
| | `project_bootstrap_pipeline.py` | 新书立项硬门禁（目录/设定/大纲/记忆/80_Projects/MEMORY） |
| | `skill_health_check.py` | skill 自检（14项项目健康检查） |
| **一致性** | `character_consistency_checker.py` | 角色OOC风险扫描 |
| | `plot_continuity_checker.py` (27KB) | 剧情逻辑/伏笔/时间线检查 |
| | `style_calibrator.py` | 风格DNA偏移检测 |
| | `physical_state_tracker.py` | 物理状态追踪（钱/物品/位置/时间一致性） |
| **流水线** | `write_pipeline.py` | 串起 pre→post 的完整写作流水线 |
| | `pipeline_utils.py` | 流水线共享工具（护照/状态/章节查找） |
| **记忆** | `memory_manager.py` (35KB) | 5层记忆模型CRUD |
| | `style_dna_extractor.py` | 从样本提取风格DNA |
| | `story_truth_manager.py` | 真相文件管理（scaffold/validate/compile/extract-delta） |
| **工具** | `name_generator.py` | 反AI同质化命名 |
| | `generate_cover.py` | Pillow封面生成(600x800) |
| | `ingest.py` (12KB) | 知识库摄入/分类/归档 |
| | `novel_review_and_upgrade.py` (31KB) | 完结复盘/规则迭代 |
| | `deconstruct_novel.py` | 拆文系统：自动分析小说提取角色/剧情/世界观/风格结构化资产 |
| **发布** | `scripts/sync_to_fanqie.py` | 同步小说到番茄发布目录 |

---

## Reference layer

`novel_creation_promax/references/` holds execution-oriented documents:

- `stages/` — Stage-organized modules (01-idea through 05-writing) with interaction templates and coherence docs
- `docs/` — Pure reference materials (not actively triggered during creation)
- `genre-templates/` — Five major genre workflows
- Standalone: `orchestrator.md`, `workflow.md`, `state-management.md`, `style-guide.md`, `technical-details.md`, `interaction.md`, `writing_constitution.md`, `chapter_constraint_template.md`, `scene-writing-card.md`, `trigger-rules.md`, `knowledge-pack-workflow.md`, `character-card-template.md`, `entity-graph-guide.md`, `genre-profile-guide.md`, `llm-keyword-retrieval.md`, `memory-relevance-filtering.md`, `override-debt-system.md`, `reading-power-taxonomy.md`, `three-stage-knowledge-filter.md`
- 注意：`opening-hooks.md`、`short-story-template.md`、`witty-style-guide.md`、`humanized-writing.md` 已迁移至 `knowledge_base/` 对应目录

**创作知识统一归口到 `knowledge_base/`（Obsidian 管理）**：
- 红线系统、评估指南 → `knowledge_base/50_Quality/`
- 题材知识库、写作技巧 → `knowledge_base/10_WorldBuilding/` + `knowledge_base/40_Writing/`
- 平台规则 → `knowledge_base/60_Platform/`

---

## Asset layer

`novel_creation_promax/assets/` stores:

- `memory_structure.json` — Canonical 5-layer memory JSON schema
- `corpus/name-database.json` (22KB) — Surname pool, given names, collision avoidance list
- `templates/` — `project-bootstrap.json` and `chapter-summary.json`
- `examples/sample-style-dna.json` — Example style DNA output
- Corpus files for specialized tone writing (毒舌知识库, 话废菩萨语料)

---

## 架构总览

```text
User Request → CLAUDE.md (auto-triggers) → SKILL.md loaded
                                              ↓
              ┌─────────────────────────────────────────┐
              │         Menu / Free Creative Flow         │
              └─────────────────────────────────────────┘
                         ↓                  ↓
         ┌─────────────────────┐  ┌───────────────────────┐
         │   References/       │  │   skills/novel-memory/   │
         │   (Knowledge Base)  │  │   (Memory Sub-skill)  │
         └─────────────────────┘  └───────────────────────┘
                         ↓                  ↓
              ┌─────────────────────────────────────────┐
              │         Python Scripts (19+ tools)        │
              └─────────────────────────────────────────┘
                         ↓
              ┌─────────────────────────────────────────┐
              │         novel_output/ (generated)         │
              └─────────────────────────────────────────┘
```

**Skill layer**：每个技能目录含一个 `SKILL.md`，带 YAML frontmatter（`name`、`description`、`dependency.python`）和定义模式/菜单/工作流/引用链接的正文。行为在调用时读取文档驱动，没有编译步骤。

---

## 关键入口

| 分类 | 文件 |
|------|------|
| **技能入口** | `skills/novel-creator/SKILL.md` · `novel_creation_promax/MODE_REGISTRY.md` · `references/orchestrator.md` · `skills/novel-review/SKILL.md` |
| **每章必读** | `references/writing_constitution.md` · `references/写作速查卡.md` · `references/chapter_constraint_template.md` |
| **记忆系统** | `skills/novel-memory/SKILL.md` · `skills/novel-memory/scripts/memory_manager.py` · `assets/memory_structure.json` · `skills/novel-memory/references/workflow_guide.md` |
| **质量约束** | `knowledge_base/50_Quality/红线检查/红线系统.md` · `knowledge_base/50_Quality/红线检查/章节前检查.md` · `knowledge_base/60_Platform/平台规则.md` |
| **模板资源** | `assets/templates/project-bootstrap.json` · `assets/templates/chapter-summary.json` · `assets/corpus/name-database.json` · `references/genre-templates/genre-specific-templates.md` |
| **知识库重点** | `knowledge_base/40_Writing/05_降AI痕迹/降低AI痕迹.md` · `knowledge_base/40_Writing/07_短篇与模板/短篇创作模板.md` · `knowledge_base/40_Writing/01_开篇技巧/开头钩子库.md` · `knowledge_base/40_Writing/风格指南/毒舌风格.md` |

### novel_output 结构检查

```bash
python tools/novel_output_audit.py              # 检查正文目录是否混入非章节产物
python tools/normalize_novel_output.py --json   # 预览低风险整理
```
