# 章节 / 场景 Spec Schema

> 用途：把“这一章写什么”从聊天任务书变成可校验的结构化输入。
> 工具：`tools/chapter_spec.py validate` / `scaffold` / `to-scene-plan`。

## 1. 章节 spec

```json
{
  "chapter": 12,
  "title": "第12章 对账",
  "summary": "200 字内本章梗概",
  "before_state": {
    "characters": [
      {"name": "姜照", "state": "被贬废卷库", "location": "废卷库"}
    ],
    "plot_hooks": ["棉衣册差额未平"]
  },
  "after_state": {
    "characters": [
      {"name": "姜照", "state": "拿到北字勘合半印", "location": "废卷库"}
    ],
    "plot_advances": ["差额指向北境饷案"]
  },
  "must_happen": ["合龙门", "发现半印"],
  "scenes": [
    {
      "type": "主要",
      "goal": "当众念平三千四百领差额",
      "result": "账平了，但秦姑姑被拖走",
      "outside": ["行动：逐项念账", "阻碍：曹福来打断", "助力：苏檀递批回", "转向：半印出现"],
      "inside": ["反应：手抖", "消化：父亲旧案", "选择：继续查", "决定：夜入废卷库"],
      "narration": "只写姜照能看到的账册与在场反应",
      "scale": "扩展"
    }
  ],
  "tension_curve": [
    {"position": 0, "value": 3, "note": "铺垫"},
    {"position": 50, "value": 8, "note": "合龙门"},
    {"position": 100, "value": 6, "note": "代价落地"}
  ],
  "change": "信息",
  "new_hooks": ["半印上的“北”字"]
}
```

### 字段规则

| 字段 | 必填 | 规则 |
|---|---|---|
| `chapter` | 是 | 正整数 |
| `title` | 是 | 非空 |
| `summary` | 是 | 非空，建议 200 字内 |
| `before_state` / `after_state` | 是 | 对象；`characters` 为数组 |
| `must_happen` | 是 | 数组；本章必须发生的事件 |
| `scenes` | 是 | 非空数组；见下 |
| `tension_curve` | 是 | 至少 2 点；`position` 0-100，`value` 1-10，按 position 升序 |
| `change` | 是 | 七选一：信息 / 关系 / 计划 / 风险 / 权力 / 理解 / 情绪 |
| `new_hooks` | 是 | 数组；本章新埋的钩子 |

### 场景规则

- `type`：主要 / 次要 / 内心 / 讲述。
- `goal` 与 `result` 必须都非空，且 **result 不能等于 goal**（每场戏必须留下差距）。
- `outside`：行动 / 阻碍 / 助力 / 转向；主要场景至少 3 轮。
- `inside`：反应 / 消化 / 选择 / 决定；不可省。
- `scale`：压缩 / 扩展。
- `narration`：旁白与视角约束。

## 2. 与场景 passport 的衔接

`tools/chapter_spec.py to-scene-plan --file spec.json --output scene_plan.json` 会把 `scenes` 转成 `tools/scene_passport.py init --plan-file` 可用的格式。

```bash
python tools/chapter_spec.py to-scene-plan --file spec.json --output scene_plan.json
python tools/scene_passport.py init --novel-dir "novel_output/番茄/书名" --chapter 12 --plan-file scene_plan.json
```

场景 passport 保存的字段：`title`、`goal`、`conflict`、`information_gain`、`hook`、`constraints`、`outcome`、`target_word_count`、`pov`、`location`、`characters`。

## 3. 与写章流水线的关系

- spec 是 **写前输入**，不替代 `write_pipeline.py pre` 的 9 问、知识包和 rule_stack。
- `context-agent` 生成任务书时应读取 spec；任务书负责“怎么写”，spec 负责“写什么”。
- 场景 passport 仍是可选门禁：只有显式初始化场景计划的章节，commit 才要求全部场景 `pass`。
- spec 不是正文、passport 或 commit 的替代品，也不由脚本直接写状态文件。

## 4. 校验

```bash
python tools/chapter_spec.py scaffold --chapter 12 --title "第12章 对账" --output spec.json
python tools/chapter_spec.py validate --file spec.json
python tools/chapter_spec.py validate --file spec.json --json
```

返回码：0 通过，1 有校验错误，2 文件不可读或 JSON 无效。
