"""Canonical templates for project-level management files."""

from __future__ import annotations


def render_project_charter(title: str, platform: str, genre: str, premise: str) -> str:
    return f"""# 项目章程 — {title}

## 项目边界

- 平台：{platform}
- 题材：{genre}
- 一句话 premise：{premise}
- 目标读者：待填写
- 预计规模：待填写

## 创作红线

- 所有角色名禁止包含“默”字。
- 设定、人物、能力和伏笔变化必须同步真相文件与项目知识库。
- 每章写后必须完成 post 审计并通过 passport 门禁。

## 里程碑

| 里程碑 | 目标 | 状态 | 验收凭证 |
|--------|------|------|----------|
| 立项 | 完成设定、大纲、风险初筛 | 进行中 | 素材/project_bootstrap_gate.json |
| 黄金三章 | 完成前 3 章并通过审计 | 未开始 | 章节 passport |
| 连载 | 稳定推进并每 5-10 章复盘 | 未开始 | 复盘报告 |

## 决策记录入口

- 主线/人物/能力/卷结构变更：记录到 `knowledge_base/80_Projects/对应项目/变更记录.md`。
- 章节级状态：以 `摘要/chapter_NNN_passport.json` 为准。
"""


def render_risk_register(title: str) -> str:
    return f"""# 风险登记表 — {title}

> 写章前扫描“开放”和“监控”项；每次复盘更新状态。

| 编号 | 风险 | 触发信号 | 影响 | 应对措施 | 责任阶段 | 状态 |
|------|------|----------|------|----------|----------|------|
| R-001 | 人物动机漂移 | 行为无法由既有欲望解释 | 高 | 对照人物档案与 OOC 清单 | 写前/写后 | 开放 |
| R-002 | 伏笔长期不回收 | 超过计划章节仍无推进 | 中 | 更新伏笔追踪总表并安排回收 | 每 5-10 章 | 监控 |
| R-003 | 现实逻辑失真 | 收入、职业、地点或流程不可信 | 高 | 对照常识约束与证据链 | 写前/审计 | 开放 |
| R-004 | 审计状态过期 | 正文被修改但 passport 仍为 pass | 高 | 重新运行 post，禁止直接续写 | 写后 | 开放 |

## 状态规范

- **开放**：必须在下一次写作前处理或明确接受风险。
- **监控**：本轮允许存在，但复盘时必须重新评估。
- **已解决**：填写解决章节、凭证和验证日期。
"""
