# 能力包（packs）

`knowledge_base/packs/<pack_id>/pack.json` 是题材/平台的**能力包契约**。它把「换平台/换题材要改什么」从脚本和 SKILL.md 里收拢到一个 manifest。

## 目录

```text
knowledge_base/packs/<pack_id>/
├── pack.json      # 必需：信号、能力、路由、坑点
└── pitfalls.md    # 必需：该包的坑点库
```

## pack.json

```json
{
  "schema_version": "1.0",
  "pack_id": "fanqie-female-romance",
  "version": "1.0.0",
  "display_name": "番茄女频现言",
  "signals": {
    "platform": "番茄",
    "genre_tags": ["现言", "婚恋", "职场"]
  },
  "capabilities": ["dialogue_heavy", "romance", "revenge"],
  "routes": {
    "dialogue": {
      "name": "对话密集",
      "trigger_capabilities": ["dialogue_heavy", "romance"],
      "files": ["knowledge_base/40_Writing/03_人物与对话/对话质感完整框架.md"]
    }
  },
  "pitfalls": "pitfalls.md"
}
```

字段说明：

| 字段 | 作用 |
|---|---|
| `signals.platform` | 与 `novel_state.platform` 匹配，计 3 分 |
| `signals.genre_tags` | 与 `novel_state.genre` 做包含匹配，每个命中计 1 分 |
| `capabilities` | 能力键；skill 只判断能力是否存在，不写题材/平台名分支 |
| `routes.<key>.trigger_capabilities` | 能力键命中时自动选中该路由；空数组表示只靠章节号/标题/细纲触发 |
| `routes.<key>.files` | 路由文件，相对项目根；被选中的文件会进入知识包 `selected_routes` |
| `pitfalls` | 域坑点库路径 |

## 选择规则

1. `novel_state.pack_id` 精确命中 → 直接使用。
2. 否则按 `signals` 计分：平台 +3，每个题材标签 +1；最高分唯一且 ≥3 → 使用；并列或低于 3 → 回退 `_ROUTES.json`。
3. 选中的包会写入 `摘要/chapter_NNN_knowledge_pack.json` 的 `pack` 字段。

## 新增一个包

1. 新建 `knowledge_base/packs/<pack_id>/pack.json` 和 `pitfalls.md`。
2. 运行 `python3 tools/pack_check.py --json` 校验引用文件。
3. 在项目 `novel_state.json` 写 `"pack_id": "<pack_id>"`（可选；不写则自动匹配）。
4. 不需要修改任何 L0 脚本或 skill。
