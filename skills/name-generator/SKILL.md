---
name: name-generator
description: 角色命名与姓名生成。用户说“起名”“角色名字”“人物命名”“取个名字”“化名”“外号”“这个名字好不好”时使用。调用 name_generator.py，避开知名角色撞名、AI 同质化命名和同音冲突，并给出命名理由。
---

# 角色命名

## 职责

只负责**人名生成、筛选、解释和入库建议**；不写正文、不改剧情、不自动创建人物档案。

命名不是找好听的字，而是回答三个问题：

1. 这个名字为什么属于这个人？（出身、家庭期望、时代、阶层）
2. 它会不会和知名角色撞名？
3. 它是不是 AI 最容易批量生成的那一类名字？

## 必读

1. `${CLAUDE_PLUGIN_ROOT}/knowledge_base/20_Characters/角色命名指南.md`
2. `${CLAUDE_PROJECT_DIR}/.claude/memory/feedback/no-mer-names.md`（如果存在）
3. 当前项目 `设定/真相文件/characters.json`（避免与已有角色同音或同风格扎堆）

## 工具

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/novel_creation_promax/scripts/name_generator.py" \
  --gender male --style ancient_elegant --count 5 --reason
```

常用参数：

| 参数 | 取值 |
|---|---|
| `--gender` | `male` / `female`；不填则随机 |
| `--style` | `ancient_elegant` `martial` `xianxia` `modern` `rustic` `dark` `gentle` `strong` `scholarly` `neutral` `urban_tech` `urban_finance` `urban_executive` |
| `--role` | `entrepreneur` `tech` `investor` `finance` `villain` `capitalist` `executive` `analyst` `parent` `child` `scholarly` `martial` `gentle` `strong` |
| `--era` | `60` `70` `80` `90` `00` `10` |
| `--surname-tier` | `common` / `literary` / `compound` |
| `--exclude-surnames` | 排除姓氏，空格分隔 |
| `--exclude-names` | 排除已有名字，空格分隔（用于反同音） |
| `--allow-overused` | 允许叶/林/苏/顾/沈等过用姓；默认不允许 |
| `--reason` | 输出命名理由 |

## 工作流

1. **收集最小输入**：性别、题材/风格、角色类型、年代、数量。用户没给时给默认值，不要一次问五个问题。
2. **读现有角色名**：从 `characters.json` 取出所有 `name` 和 `aliases`，作为 `--exclude-names`。
3. **跑脚本**：默认 `--count 5 --reason`。
4. **检查输出**：
   - `ai_pattern_warning` 不为空 → 该名字是 AI 高发模式，换掉。
   - `surname_overused=true` → 同一本书里不要连续出现两个过用姓。
   - 与现有名字同音 → 换掉。
5. **必要时重跑**：加 `--exclude-names`、`--surname-tier common`，或换 `--style`。
6. **输出表格**：姓名 / 姓 / 名 / 含义 / 命名理由 / 风险。
7. **用户选定后**才交接给立项或章节主流程，由其按既有真相/记忆流水线纳入项目角色卡和人物数据，交接字段至少包含：
   - `name`
   - `aliases`（如有）
   - `name_reason`
   - `name_style`
   - `name_risk`（撞名/AI 模式/同音检查结果）

## 硬规则

- **强制触发**：立项、短篇、续写、改稿中新增具名角色，或为角色新增化名、外号时，必须加载本技能并实际执行 `name_generator.py`，不得仅凭模型直接起名或口头声称检查通过。正文中临时出现的新角色也适用；只有功能称呼的无名人物无需生成姓名。
- **已有与指定姓名**：已有角色沿用姓名不重新生成；用户指定姓名、导入原作姓名不擅自替换，但新增入项目时仍须调用本技能检查禁字、撞名和同音风险，发现冲突先向用户说明，解决后才能使用。
- **检查留痕**：在工作区 `素材/命名记录.md` 记录角色用途、候选名、实际脚本命令、输出中的检查结果、额外禁字/同音核查结果与用户选定结果；脚本失败或风险未解决时停止采用新名字，不得伪造成功记录。
- **写入边界**：用户选定后，由立项或章节主流程通过既有真相/记忆流水线同步人物信息；本技能不得直接改写受保护的真相文件或状态文件。
- 名字中**禁止出现“默”字**（见 `.claude/memory/feedback/no-mer-names.md`）。
- 禁止使用知名角色名：萧炎、叶凡、林动、唐三、石昊、韩立、梅长苏、甄嬛、若曦、魏璎珞、白浅、夜华、魏无羡、蓝忘机等；完整名单由脚本 `avoid_list` 检查。
- 禁止 AI 四件套：子轩/子涵/子墨/子豪、若雪/若曦/若烟/若兮、墨寒/墨渊/墨白/墨尘、语嫣/诗涵/紫萱/梦瑶。
- 配角名字不能比主角更抢戏；工具人用功能称呼，不要硬起文艺名。
- 每个名字必须有**作品内理由**；没有理由的名字就是 AI 名字。
- 不自动创建人物，不把候选名直接写进正文。
- 不写入 `${CLAUDE_PLUGIN_ROOT}/knowledge_base/`；项目角色信息只写工作区。

## 输出示例

```text
| 姓名 | 姓 | 名 | 含义 | 命名理由 | 风险 |
|---|---|---|---|---|---|
| 曹知远 | 曹 | 知远 | 知行致远 | 枭雄姓 + 书卷名，适合谋士型配角 | 无 |
| 赵明诚 | 赵 | 明诚 | 自明诚谓之性 | 大姓 + 稳重名，适合家族长子 | 无 |
```

用户选定后，交接给立项或章节主流程统一落盘，无需对同一项已获授权的命名重复确认。

## 边界

- 只处理人名；地名、势力名、书名、章节名不在本 skill 范围。
- 不评价名字“好不好听”；只评价是否撞名、是否 AI 高发、是否符合人物。
- 不替代角色设计；人物的动机、弧线、声线仍由角色档案和 `人物声线与弧线卡.md` 负责。
