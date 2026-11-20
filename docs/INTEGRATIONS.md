# 外部集成（MCP / 浏览器 / 知识库）

> **按需文档**：本文件不在会话启动时加载。

---

## MCP 服务器配置

`.claude/settings.json` 中预置共享 MCP 服务器，机器本地凭据放在 **不入库** 的 `.claude/settings.local.json`：

- **`chrome-devtools`** — Chrome 浏览器自动化（用于发布验证、竞品调研、故障排查）→ 在 `settings.json`
- **`lark-mcp`** — 飞书 Lark API（用于读取飞书文档/wiki、操作多维表格）→ 在 `settings.local.json`（含 app_secret，已被 `.gitignore` 忽略）

> ⚠️ **禁止把 app_secret / token 写进 `settings.json`**。`tools/health_check.py` 第 3 项会全仓正则扫描明文凭据。

**使用规范**：
- 使用 `browser_navigate` + `browser_screenshot` 进行页面验证
- 不要读取包含敏感隐私的页面（仅限小说创作相关操作）
- 飞书工具凭据已配置，可直接调用读取文档

---

## 🤖 ThirdSpace MCP 知识库

**项目路径**：`/tmp/thirdspace-pub/`
**Vault 路径**：`knowledge_base/space/`（原生内容）+ `knowledge_base/flux/`（原始数据）

**核心 MCP 工具**：
- `add_note` — 快速添加笔记到指定主题
- `collect_content` — 抓取网页原文（IO）
- `save_knowledge_card` — 保存 AI 生成的知识卡片
- `list_topics` — 查看所有主题及统计
- `manage_topic` — 主题 CRUD + 合并建议
- `gather_reflections` — 采集深度思考素材
- `create_worklog` — 创建工作日志
- `weekly_review` — 周复盘聚合数据
- `add_action` / `check_action` — 行动打卡追踪

**预设主题**：AI 技术、小说创作、阅读学习、工作记录、日记反思、灵感想法、工具技巧、项目管理

**使用流程**：
1. 用户发文章链接 → AI 自动抓取 → 生成知识卡片 → 保存到 `space/found/`
2. 用户记录想法 → AI 自动分类到对应主题 → 保存到 `space/crafted/`
3. 定期反思 → AI 读取知识卡片 → 生成 Mirror/Deepen/Bridge 反思 → 保存到主题目录

---

## 👁️ 浏览器自动化 (Chrome DevTools MCP)

**工具**：`chrome-devtools-mcp` (已配置在 `.claude/settings.json`)

**能力**：
您拥有完整的 Chrome 浏览器控制权。

**使用场景**：
1.  **发布验证**：发布章节后，打开番茄作家后台，检查内容是否渲染正确。
2.  **竞品调研**：打开番茄/起点/七猫网页，抓取榜单数据、分析爆款书名/简介。
3.  **故障排除**：如果发布脚本报错，打开浏览器查看具体的控制台报错或网络请求。

**操作规范**：
- 使用 `browser_navigate` 打开网页。
- 使用 `browser_screenshot` 查看当前页面状态（“眼见为实”）。
- 使用 `browser_click` / `browser_type` 进行交互。
- **安全提示**：不要读取包含敏感隐私的页面（如个人银行账户），仅限小说创作相关操作。

---

## 🧠 LLM Wiki 知识库（Karpathy 模式）

本项目集成 Karpathy LLM Wiki 模式。全局知识库位于 `~/.openclaw/knowledge-base/`。

### 知识库结构

```
~/.openclaw/knowledge-base/
├── CLAUDE.md          ← wiki schema（维护规则）
├── raw/               ← 原始素材（只读）
│   ├── papers/
│   └── tutorials/
├── wiki/              ← LLM 维护的结构化知识
│   ├── sources/       来源摘要
│   ├── tools/         工具评测
│   ├── techniques/    技术概念
│   ├── projects/      项目档案
│   └── index.md       全局索引
└── logs/              变更记录
```

### 三大工作流

#### 1. Ingest（摄取）
当用户说"学一篇"、"分析这篇"或往 `raw/` 放入新文件时：
1. 读取原始素材
2. 在 `wiki/sources/` 创建摘要页面
3. 更新相关的 `wiki/tools/`、`wiki/techniques/` 页面
4. 更新 `wiki/index.md`
5. 在 `logs/CHANGELOG.md` 追加记录

#### 2. Query（查询）
当用户提问技术问题（爬虫、AI 工具、架构等）时：
1. 先查 `wiki/index.md`
2. 读取对应的 wiki 页面
3. 给出有 `[[wikilink]]` 引用标记的回答

#### 3. Lint（巡检）
当用户说"巡检"时：
1. 检查各页面 `updated` 日期
2. 标记矛盾/过时/孤立页面
3. 输出巡检报告

### 使用规范
- 用 `[[wikilink]]` 格式交叉引用
- 文件名用 `kebab-case.md`
- 每个页面顶部必须有 YAML frontmatter
- 发现新知识时主动更新 wiki，不要只记在对话里
