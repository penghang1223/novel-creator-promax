# 番茄小说自动发布（桥接层）

本目录不内置第三方 Playwright 发布引擎，`publish.py` / `login.py` 是**桥接入口**：
它们解析一个外部 `fanqie_auto_publish` 引擎，并以工作区为运行目录执行。

这样做的原因：

- Playwright 发布引擎体积大、更新频繁，不适合随插件一起分发；
- 登录态、章节草稿和已发布归档必须留在用户工作区，不能写进只读插件目录。

## 引擎解析顺序

1. `NOVEL_FANQIE_PUBLISHER`：指向引擎的 `publish.py` 或其所在目录
2. `~/fanqie_auto_publish/`
3. `{workspace}/.novel_publish/fanqie/engine/`
4. `auto_publish/fanqie_auto_publish/engine/`

```bash
export NOVEL_FANQIE_PUBLISHER="$HOME/fanqie_auto_publish"
```

## 工作区目录

所有运行产物都在工作区，不在插件目录：

```text
{workspace}/.novel_publish/fanqie/
├── state.json          # 登录态（首次运行会从引擎目录复用）
├── chapters/           # 长篇小说章节（sync_to_fanqie.py 生成）
├── short_chapters/     # 短故事章节
├── uploaded/           # 已发布长篇章归档
└── short_uploaded/     # 已发布短故事归档
```

## 安装

```bash
python3 -m pip install -r requirements.txt
python3 -m playwright install chromium
```

## 使用

```bash
# 1. 首次登录（扫码后回车保存登录态）
python3 auto_publish/fanqie_auto_publish/login.py

# 2. 从 novel_output 同步待发章节到工作区发布目录
python3 scripts/sync_to_fanqie.py "书名"
python3 scripts/sync_to_fanqie.py --short "短故事名"

# 3. 存草稿（推荐先草稿）
python3 auto_publish/fanqie_auto_publish/publish.py --book "书名" --count 3 --draft

# 4. 明确授权后直接发布
python3 auto_publish/fanqie_auto_publish/publish.py --book "书名" --count 3

# 5. 只检查引擎与依赖
python3 auto_publish/fanqie_auto_publish/publish.py --check
```

## 安全边界

- 未经用户明确授权，不执行直接发布；默认只做草稿。
- 登录态和 cookies 只存工作区，不提交、不写插件目录。
- 发布前必须通过 `write_pipeline.py post` 并存在 accepted commit；未审计章节不得同步。
