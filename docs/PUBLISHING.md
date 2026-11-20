# 发布与可视化面板

> **按需文档**：本文件不在会话启动时加载。

---

## 📤 自动发布模块

支持 **番茄小说**、**起点中文网**、**知乎盐选**、**七猫免费小说** 四个平台。所有发布工具均基于 Playwright。

### 番茄小说 (`auto_publish/fanqie_auto_publish/`)

**登录**：
```bash
cd auto_publish/fanqie_auto_publish
.venv/bin/python3 login.py
```

**小说连载发布**：
```bash
.venv/bin/python3 publish.py --book "书名" --draft    # 存草稿
.venv/bin/python3 publish.py --book "书名" --count 3  # 发布3章
```

**短故事发布**（合并所有章节为一个文档，`<h1>` 分隔）：
```bash
.venv/bin/python3 publish.py --short --book "短故事名" --draft
.venv/bin/python3 publish.py --short --book "短故事名"
```

**目录结构**：`chapters/`、`short_chapters/`、`uploaded/`、`short_uploaded/`

### 起点中文网 (`auto_publish/qidian_auto_publish/`)

**登录**（QQ 扫码）：
```bash
cd auto_publish/qidian_auto_publish
.venv/bin/python3 login.py
```

**发布**：
```bash
.venv/bin/python3 publish.py --book "书名" --count 3
.venv/bin/python3 publish.py --book "书名" --draft
```

**目录结构**：`chapters/`、`uploaded/`

### 知乎盐选 (`auto_publish/zhihu_auto_publish/`)

> 仅支持**签约后**发布。首次投稿需手动完成。

**登录**：
```bash
cd auto_publish/zhihu_auto_publish
.venv/bin/python3 login.py
```

**发布**：
```bash
.venv/bin/python3 publish.py --book "作品名" --count 5
.venv/bin/python3 publish.py --book "作品名" --draft
```

**目录结构**：`chapters/`、`uploaded/`

### 七猫免费小说 (`auto_publish/qimao_auto_publish/`)

**登录**（手机号 + 验证码/密码）：
```bash
cd auto_publish/qimao_auto_publish
python3 login.py
```

**发布**：
```bash
python3 publish.py --book "书名" --count 3
python3 publish.py --book "书名" --draft
```

**目录结构**：`chapters/`、`uploaded/`

### 通用发布参数

| 参数 | 说明 |
|------|------|
| `--book "书名"` | 指定书名（自动选择，跳过交互） |
| `--count N` | 发布章节数量 |
| `--draft` | 存草稿模式（不直接发布） |
| `--no-close` | 不关闭浏览器（便于调试） |

### 发布同步工具

将 `novel_output/` 中的小说同步到发布目录：
```bash
python scripts/sync_to_fanqie.py              # 同步所有小说
python scripts/sync_to_fanqie.py --short      # 同步所有短故事
python scripts/sync_to_fanqie.py "书名"        # 同步指定小说
```

---

## 🖥️ Web Dashboard (可视化工作流面板)

FastAPI 后端 + React/TypeScript/Vite/Tailwind 前端，提供看板、编辑器、流水线控制。

- **后端**：`web_dashboard/backend/` — FastAPI app，含 chapters/memory/novels/pipeline/WebSocket 路由
- **前端**：`web_dashboard/frontend/` — React + TypeScript + Vite + Tailwind，含 kanban/dashboard/editor 页面

**启动方式**：

```bash
# 后端（终端 1）
cd web_dashboard/backend
uvicorn main:app --reload --port 8000

# 前端（终端 2，开发模式）
cd web_dashboard/frontend
npm install
npm run dev
```

生产模式：`npm run build` 后产物自动 mount 到 FastAPI 静态路由。
