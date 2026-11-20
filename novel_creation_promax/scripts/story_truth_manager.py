#!/usr/bin/env python3
"""
Story truth file manager.

This script turns setting material into deterministic project artifacts:
- scaffold: create structured truth files under 设定/真相文件
- validate: block writing when truth files are missing, thin, or still placeholders
- compile: create chapter-level rule_stack + truth brief before writing
- extract-delta: scan chapter text and attach candidate fact changes to truth_delta
- validate-delta/apply-delta: force post-chapter fact extraction and sync
- normalize: create a structured补写/压缩任务 when chapter length is outside range
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

from pipeline_utils import count_chinese_chars, find_chapter_file, load_json, now_iso, save_json


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


PROJECT_ROOT = Path(__file__).resolve().parents[2]
from novel_creation_promax.core import thresholds as T  # noqa: E402
from novel_creation_promax.core.roots import workspace_root  # noqa: E402

TRUTH_DIR_NAME = "真相文件"
WORD_COUNT_MIN = T.WORD_COUNT_MIN
WORD_COUNT_MAX = T.WORD_COUNT_MAX
WORD_COUNT_TARGET = T.WORD_COUNT_TARGET

EVIDENCE_LEVELS = ("confirmed", "inferred", "assumed")
EVIDENCE_POLICY = {
    "levels": list(EVIDENCE_LEVELS),
    "confirmed": "来自真相文件、细纲或上一章正文",
    "inferred": "来自题材惯例或风格 DNA，必须能说明依据",
    "assumed": "模型猜测，禁止进入正文",
}

PLACEHOLDERS = [
    "TODO",
    "TBD",
    "待填写",
    "待补全",
    "未填写",
    "未确定",
    "占位",
    "这里填写",
    "示例：",
    "示例:",
]

TRUTH_FILE_RULES: dict[str, dict[str, Any]] = {
    "characters.json": {
        "kind": "characters",
        "min_records": 2,
        "required_fields": [
            "id",
            "name",
            "role",
            "occupation",
            "income_range",
            "residence",
            "reality_anchor",
            "motivation",
            "speech_style",
            "behavior_rules",
        ],
    },
    "locations.json": {
        "kind": "locations",
        "min_records": 2,
        "required_fields": ["id", "name", "type", "cost_level", "access_rules", "real_world_rules"],
    },
    "factions.json": {
        "kind": "factions",
        "min_records": 1,
        "required_fields": ["id", "name", "type", "resources", "limits", "interests", "action_boundary"],
    },
    "events.json": {
        "kind": "events",
        "min_records": 1,
        "required_fields": ["id", "name", "status", "cause", "effect", "evidence_chain", "affected_entities"],
    },
    "relationships.json": {
        "kind": "relationships",
        "min_records": 2,
        "required_fields": ["id", "source", "target", "type", "trust_level", "conflict", "information_gap"],
    },
    "resources.json": {
        "kind": "resources",
        "min_records": 1,
        "required_fields": ["id", "owner", "type", "quantity_or_level", "limits", "cost"],
    },
    "foreshadowing.json": {
        "kind": "foreshadowing",
        "min_records": 1,
        "required_fields": ["id", "plant_chapter", "content", "payoff_plan", "status", "risk_if_forgotten"],
    },
}


def resolve_path(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else workspace_root() / p


def rel(path: Path, root: Path | None = None) -> str:
    root = root or workspace_root()
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def truth_dir(novel_dir: Path) -> Path:
    return novel_dir / "设定" / TRUTH_DIR_NAME


def has_placeholder(value: Any) -> bool:
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    return any(token in text for token in PLACEHOLDERS)


def is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


def base_payload(kind: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "kind": kind,
        "source": "project_bootstrap",
        "updated_at": now_iso(),
        "records": records,
        "chapter_facts": [],
        "pending_updates": [],
        "open_questions": [],
    }


def truth_templates(title: str) -> dict[str, dict[str, Any]]:
    return {
        "characters.json": base_payload(
            "characters",
            [
                {
                    "id": "char_001",
                    "name": "待填写",
                    "role": "主角/核心配角/反派",
                    "age": "待填写",
                    "occupation": "待填写",
                    "income_range": "待填写",
                    "residence": "待填写",
                    "education_or_skill": "待填写",
                    "reality_anchor": {
                        "income_housing_logic": "解释收入、房租/房贷、居住选择为什么成立",
                        "job_logic": "解释入职、晋升、被裁、转岗、创业等职业变化的可信原因",
                        "daily_schedule": "待填写",
                        "resources": ["待填写"],
                        "constraints": ["待填写"],
                    },
                    "motivation": {
                        "external_goal": "待填写",
                        "inner_desire": "待填写",
                        "core_fear": "待填写",
                        "bottom_line": "待填写",
                    },
                    "speech_style": {
                        "tone": "待填写",
                        "sentence_pattern": "待填写",
                        "professional_words": ["待填写"],
                        "forbidden_lines": ["不符合身份、学历、职业、情绪状态的话"],
                    },
                    "behavior_rules": {
                        "will_do": ["待填写"],
                        "will_not_do": ["待填写"],
                        "stress_response": "待填写",
                        "decision_logic": "待填写",
                    },
                    "current_state": {
                        "chapter": 0,
                        "location": "待填写",
                        "emotion": "待填写",
                        "assets": ["待填写"],
                    },
                    "knowledge_boundary": [],
                    "secrets": [],
                    "power_ladder": [
                        {
                            "level": "当前层级",
                            "abilities": [],
                            "cost": "",
                            "obtained_chapter": 0,
                            "cannot_beat": [],
                        }
                    ],
                }
            ],
        ),
        "locations.json": base_payload(
            "locations",
            [
                {
                    "id": "loc_001",
                    "name": "待填写",
                    "type": "住处/公司/学校/店铺/公共空间/秘密地点",
                    "city_or_region": "待填写",
                    "cost_level": "房租/消费/通勤成本待填写",
                    "access_rules": "谁能进入、需要什么权限、是否有监控或门禁",
                    "real_world_rules": "收入、距离、时间、消费水平、治安等常识约束",
                    "scene_uses": ["谈判", "冲突", "调查", "休整"],
                }
            ],
        ),
        "factions.json": base_payload(
            "factions",
            [
                {
                    "id": "fac_001",
                    "name": "待填写",
                    "type": "公司/家族/平台/监管/帮派/行业圈层",
                    "leader": "待填写",
                    "resources": ["钱、人、渠道、技术、舆论或法律资源"],
                    "limits": ["不能无成本调动所有资源"],
                    "interests": "待填写",
                    "action_boundary": "行动需要的理由、流程、代价和风险",
                }
            ],
        ),
        "events.json": base_payload(
            "events",
            [
                {
                    "id": "evt_001",
                    "name": "待填写",
                    "status": "planned",
                    "chapter_range": "待填写",
                    "cause": "谁推动、为什么发生",
                    "effect": "影响哪些人、地点、势力、资源和后续选择",
                    "evidence_chain": ["证据、证人、文件、数据、物品或谣言"],
                    "affected_entities": ["char_001"],
                    "debts": ["后续必须偿还的剧情债"],
                    "reader_known": False,
                    "reveal_status": "未揭示",
                    "reveal_chapter": None,
                }
            ],
        ),
        "relationships.json": base_payload(
            "relationships",
            [
                {
                    "id": "rel_001",
                    "source": "char_001",
                    "target": "待填写",
                    "type": "亲属/同事/敌对/合作/暧昧/债务/师徒",
                    "trust_level": 0,
                    "conflict": "待填写",
                    "information_gap": "双方分别知道什么、不知道什么、误以为什么",
                    "change_rules": "什么事件会让关系升温、破裂、反转或结盟",
                }
            ],
        ),
        "resources.json": base_payload(
            "resources",
            [
                {
                    "id": "res_001",
                    "owner": "char_001/fac_001",
                    "type": "现金/资产/技能/权限/人脉/道具/系统能力",
                    "quantity_or_level": "待填写",
                    "limits": "使用条件、冷却、法律/伦理/成本边界",
                    "cost": "每次使用要付出的代价",
                    "visibility": "谁知道它存在",
                }
            ],
        ),
        "foreshadowing.json": base_payload(
            "foreshadowing",
            [
                {
                    "id": "foreshadow_001",
                    "plant_chapter": 1,
                    "content": "待填写",
                    "payoff_plan": "预计回收章节、方式和读者爽点",
                    "status": "planned",
                    "linked_entities": ["char_001"],
                    "risk_if_forgotten": "忘记会造成的设定漂移或剧情断裂",
                    "reader_known": True,
                    "reveal_status": "未揭示",
                    "reveal_chapter": None,
                }
            ],
        ),
    }


def scaffold_truth_files(novel_dir: Path, *, title: str = "", force: bool = False) -> list[Path]:
    target_dir = truth_dir(novel_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    payloads = truth_templates(title or novel_dir.name)
    written: list[Path] = []
    for file_name, payload in payloads.items():
        path = target_dir / file_name
        if path.exists() and not force:
            continue
        save_json(path, payload)
        written.append(path)
    index_path = target_dir / "README.md"
    if force or not index_path.exists():
        index_path.write_text(
            f"""# {title or novel_dir.name} 真相文件

这些 JSON 是正文写作的事实源，不是灵感草稿。

- `characters.json`: 人物现实锚点、动机、声纹、行为边界
- `locations.json`: 地点成本、通勤、权限、场景用途
- `factions.json`: 势力资源、利益、行动边界
- `events.json`: 事件因果、证据链、剧情债
- `relationships.json`: 信任、冲突、信息差、关系变化规则
- `resources.json`: 金钱、技能、权限、道具、系统能力及代价
- `foreshadowing.json`: 伏笔埋设、回收计划、遗忘风险

写第 N 章前运行 `write_pipeline.py pre` 会编译本章 `rule_stack`；写后必须补齐 `chapter_NNN_truth_delta.json`。
""",
            encoding="utf-8",
        )
        written.append(index_path)
    return written


def validate_truth_files(novel_dir: Path) -> dict[str, Any]:
    target_dir = truth_dir(novel_dir)
    results: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for file_name, rule in TRUTH_FILE_RULES.items():
        path = target_dir / file_name
        item: dict[str, Any] = {
            "file": rel(path, novel_dir),
            "status": "pass",
            "detail": "ok",
            "records": 0,
        }
        payload = load_json(path, None)
        failures: list[str] = []
        if not path.exists():
            failures.append("文件不存在")
        elif not isinstance(payload, dict):
            failures.append("JSON 无效或顶层不是 object")
        else:
            if payload.get("kind") != rule["kind"]:
                failures.append(f"kind 应为 {rule['kind']}")
            records = payload.get("records")
            if not isinstance(records, list):
                failures.append("records 必须是数组")
                records = []
            item["records"] = len(records)
            if len(records) < int(rule["min_records"]):
                failures.append(f"records 不足 {len(records)}<{rule['min_records']}")
            if has_placeholder(payload):
                failures.append("仍含占位词")
            for idx, record in enumerate(records, 1):
                if not isinstance(record, dict):
                    failures.append(f"record #{idx} 不是 object")
                    continue
                missing = [field for field in rule["required_fields"] if is_blank(record.get(field))]
                if missing:
                    failures.append(f"record #{idx} 缺少字段: {', '.join(missing)}")
                record_id = str(record.get("id", "")).strip()
                if not record_id:
                    failures.append(f"record #{idx} id 为空")
                elif record_id in seen_ids:
                    failures.append(f"id 重复: {record_id}")
                else:
                    seen_ids.add(record_id)
                if file_name == "characters.json":
                    name = str(record.get("name", ""))
                    if "默" in name:
                        failures.append(f"角色名含禁字: {name}")

        if failures:
            item["status"] = "fail"
            item["detail"] = "；".join(failures[:8])
        results.append(item)

    failed = [item for item in results if item["status"] != "pass"]
    return {
        "generated_at": now_iso(),
        "truth_dir": rel(target_dir, novel_dir),
        "status": "pass" if not failed else "fail",
        "passed": len(results) - len(failed),
        "failed": len(failed),
        "results": results,
    }


def collect_records(novel_dir: Path) -> dict[str, list[dict[str, Any]]]:
    records: dict[str, list[dict[str, Any]]] = {}
    for file_name, rule in TRUTH_FILE_RULES.items():
        payload = load_json(truth_dir(novel_dir) / file_name, {})
        value = payload.get("records", []) if isinstance(payload, dict) else []
        records[rule["kind"]] = value if isinstance(value, list) else []
    return records


def _critical_flag(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() not in {"false", "0", "no", "warning", "warn"}
    return bool(value)


def normalize_open_question(
    raw: Any,
    *,
    file_name: str,
    kind: str,
    index: int,
) -> dict[str, Any] | None:
    """Normalize one truth-file open question into a blocker candidate."""
    if isinstance(raw, str):
        reason = raw.strip()
        if not reason:
            return None
        return {
            "id": f"{file_name}:open:{index}",
            "file": file_name,
            "kind": kind,
            "entity_id": "",
            "field": "",
            "reason": reason,
            "critical": True,
            "chapters": [],
            "source": "open_questions",
        }
    if not isinstance(raw, dict):
        return None
    reason = raw.get("reason") or raw.get("question") or raw.get("description")
    if is_blank(reason):
        return None
    chapters: list[int] = []
    raw_chapters = raw.get("chapters") or []
    if isinstance(raw_chapters, (int, str)):
        raw_chapters = [raw_chapters]
    elif not isinstance(raw_chapters, list):
        raw_chapters = []
    for value in raw_chapters:
        try:
            number = int(value)
        except (TypeError, ValueError):
            continue
        if number >= 1:
            chapters.append(number)
    return {
        "id": str(raw.get("id") or f"{file_name}:open:{index}"),
        "file": file_name,
        "kind": kind,
        "entity_id": str(raw.get("entity_id") or ""),
        "field": str(raw.get("field") or ""),
        "reason": str(reason).strip(),
        "critical": _critical_flag(raw.get("critical", True)),
        "chapters": chapters,
        "source": "open_questions",
    }


def collect_unknown_facts(novel_dir: Path, chapter: int) -> list[dict[str, Any]]:
    """Collect explicit and status-based unknowns from all truth files.

    ``open_questions`` is the explicit channel:

    ```json
    {"entity_id": "char_001", "field": "motivation", "reason": "...", "critical": true}
    ```

    Records with ``status: "unknown"`` are also reported. Facts scoped with
    ``chapters`` only apply to those chapters; unscoped critical facts block
    every chapter until resolved.
    """
    facts: list[dict[str, Any]] = []
    for file_name, rule in TRUTH_FILE_RULES.items():
        payload = load_json(truth_dir(novel_dir) / file_name, {})
        if not isinstance(payload, dict):
            continue
        for index, raw in enumerate(payload.get("open_questions") or [], 1):
            fact = normalize_open_question(
                raw, file_name=file_name, kind=rule["kind"], index=index
            )
            if fact is not None and (not fact["chapters"] or chapter in fact["chapters"]):
                facts.append(fact)
        records = payload.get("records")
        if not isinstance(records, list):
            continue
        for record in records:
            if not isinstance(record, dict):
                continue
            if str(record.get("status", "")).strip().lower() not in {"unknown", "待定"}:
                continue
            fact = {
                "id": f"{file_name}:{record.get('id', '')}:status",
                "file": file_name,
                "kind": rule["kind"],
                "entity_id": str(record.get("id") or ""),
                "field": "status",
                "reason": str(record.get("unknown_reason") or "记录状态为 unknown"),
                "critical": _critical_flag(record.get("critical", True)),
                "chapters": [],
                "source": "record_status",
            }
            facts.append(fact)
    return facts


def _reveal_fields(record: dict[str, Any], chapter: int, *, default_reader_known: bool) -> tuple[bool, str, int | None, bool]:
    reveal_chapter: int | None = None
    raw_chapter = record.get("reveal_chapter")
    if raw_chapter is not None:
        try:
            reveal_chapter = int(raw_chapter)
        except (TypeError, ValueError):
            reveal_chapter = None
    status = str(record.get("reveal_status") or "").strip()
    if reveal_chapter is not None and reveal_chapter > chapter:
        return False, status or "未揭示", reveal_chapter, False
    explicit = record.get("reader_known")
    if isinstance(explicit, bool):
        return explicit, status or ("已揭示" if explicit else "未揭示"), reveal_chapter, status == "部分揭示"
    if status:
        known = status in {"已揭示", "部分揭示"}
        return known, status, reveal_chapter, status == "部分揭示"
    return default_reader_known, "已揭示" if default_reader_known else "未揭示", reveal_chapter, False


def collect_truth_layers(novel_dir: Path, chapter: int) -> dict[str, Any]:
    """Split truth records into author truth, reader-known facts and unrevealed facts.

    ``events.json`` describes what happened. ``reader_known`` / ``reveal_status`` /
    ``reveal_chapter`` decide whether the reader (and therefore characters) may
    use it at this chapter. ``foreshadowing.json`` produces a visible hook entry
    and an author-only payoff entry.
    """
    entries: list[dict[str, Any]] = []

    events_payload = load_json(truth_dir(novel_dir) / "events.json", {})
    for record in (events_payload.get("records") if isinstance(events_payload, dict) else []) or []:
        if not isinstance(record, dict):
            continue
        known, status, reveal_chapter, partial = _reveal_fields(record, chapter, default_reader_known=True)
        entries.append(
            {
                "type": "event",
                "id": str(record.get("id") or ""),
                "name": str(record.get("name") or ""),
                "summary": str(record.get("effect") or record.get("cause") or record.get("name") or ""),
                "reader_known": known,
                "reveal_status": status,
                "reveal_chapter": reveal_chapter,
                "partial": partial,
                "source": "events.json",
            }
        )

    foreshadow_payload = load_json(truth_dir(novel_dir) / "foreshadowing.json", {})
    for record in (foreshadow_payload.get("records") if isinstance(foreshadow_payload, dict) else []) or []:
        if not isinstance(record, dict):
            continue
        planted = record.get("plant_chapter")
        try:
            planted_chapter = int(planted) if planted is not None else None
        except (TypeError, ValueError):
            planted_chapter = None
        hook_known = planted_chapter is None or planted_chapter <= chapter
        entries.append(
            {
                "type": "foreshadowing_hook",
                "id": str(record.get("id") or ""),
                "name": str(record.get("id") or ""),
                "summary": str(record.get("content") or ""),
                "reader_known": hook_known,
                "reveal_status": "已埋" if hook_known else "未埋",
                "reveal_chapter": planted_chapter,
                "partial": False,
                "source": "foreshadowing.json",
            }
        )
        status = str(record.get("status") or "").strip()
        if status not in {"resolved", "已回收", "已过期", "放弃"}:
            entries.append(
                {
                    "type": "foreshadowing_payoff",
                    "id": str(record.get("id") or ""),
                    "name": str(record.get("id") or ""),
                    "summary": str(record.get("payoff_plan") or ""),
                    "reader_known": False,
                    "reveal_status": str(record.get("reveal_status") or "未揭示"),
                    "reveal_chapter": None,
                    "partial": False,
                    "source": "foreshadowing.json",
                }
            )

    characters_payload = load_json(truth_dir(novel_dir) / "characters.json", {})
    character_knowledge: dict[str, Any] = {}
    for record in (characters_payload.get("records") if isinstance(characters_payload, dict) else []) or []:
        if not isinstance(record, dict):
            continue
        identity = str(record.get("id") or record.get("name") or "")
        if not identity:
            continue
        character_knowledge[identity] = {
            "name": str(record.get("name") or identity),
            "knows": [str(item) for item in (record.get("knowledge_boundary") or []) if str(item).strip()],
            "author_only": [str(item) for item in (record.get("secrets") or []) if str(item).strip()],
            "power_ladder": [
                dict(item) for item in (record.get("power_ladder") or []) if isinstance(item, dict)
            ],
        }

    reader_known = [item for item in entries if item["reader_known"]]
    unrevealed = [item for item in entries if not item["reader_known"]]
    return {
        "author_truth": entries,
        "reader_known": reader_known,
        "unrevealed_facts": unrevealed,
        "character_knowledge": character_knowledge,
        "stats": {
            "author_truth": len(entries),
            "reader_known": len(reader_known),
            "unrevealed": len(unrevealed),
            "characters": len(character_knowledge),
        },
    }


def compact(value: Any, max_len: int = 220) -> str:
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= max_len else text[: max_len - 1] + "…"


def compile_rule_stack(novel_dir: Path, chapter: int, title: str = "") -> dict[str, Any]:
    records = collect_records(novel_dir)
    state = load_json(novel_dir / "novel_state.json", {})
    word_range = state.get("word_count_range") if isinstance(state, dict) else None
    if not isinstance(word_range, list) or len(word_range) != 2:
        word_range = [WORD_COUNT_MIN, WORD_COUNT_MAX]

    active_rules: list[dict[str, Any]] = [
        {
            "id": "word_count_fanqie",
            "level": "hard",
            "rule": f"正文中文字符必须在 {word_range[0]}-{word_range[1]}，首稿瞄准 {WORD_COUNT_TARGET} 左右。",
        },
        {
            "id": "no_step_skip",
            "level": "hard",
            "rule": "必须按 pre -> 正文 -> chapter_summary -> truth_delta -> post 的顺序交付。",
        },
        {
            "id": "no_truth_drift",
            "level": "hard",
            "rule": "人物台词、行为、收入居住、职业变动、势力行动、事件因果不得违背真相文件。",
        },
        {
            "id": "no_mer_names",
            "level": "hard",
            "rule": "新角色名禁止包含“默”字。",
        },
    ]

    for character in records.get("characters", [])[:8]:
        active_rules.append(
            {
                "id": f"character:{character.get('id', '')}",
                "level": "hard",
                "rule": compact(
                    {
                        "name": character.get("name"),
                        "role": character.get("role"),
                        "reality_anchor": character.get("reality_anchor"),
                        "motivation": character.get("motivation"),
                        "speech_style": character.get("speech_style"),
                        "behavior_rules": character.get("behavior_rules"),
                        "power_ladder": character.get("power_ladder"),
                    },
                    520,
                ),
            }
        )
    for location in records.get("locations", [])[:6]:
        active_rules.append(
            {
                "id": f"location:{location.get('id', '')}",
                "level": "hard",
                "rule": compact(
                    {
                        "name": location.get("name"),
                        "cost_level": location.get("cost_level"),
                        "access_rules": location.get("access_rules"),
                        "real_world_rules": location.get("real_world_rules"),
                    },
                    360,
                ),
            }
        )
    for faction in records.get("factions", [])[:6]:
        active_rules.append(
            {
                "id": f"faction:{faction.get('id', '')}",
                "level": "hard",
                "rule": compact(
                    {
                        "name": faction.get("name"),
                        "resources": faction.get("resources"),
                        "limits": faction.get("limits"),
                        "action_boundary": faction.get("action_boundary"),
                    },
                    360,
                ),
            }
        )
    for relation in records.get("relationships", [])[:10]:
        active_rules.append(
            {
                "id": f"relationship:{relation.get('id', '')}",
                "level": "hard",
                "rule": compact(relation, 320),
            }
        )

    unknown_facts = collect_unknown_facts(novel_dir, chapter)
    for fact in unknown_facts:
        fact.setdefault("evidence_level", "assumed")
    critical_unknown = [item for item in unknown_facts if item.get("critical")]
    assumed_facts = [
        item
        for item in unknown_facts
        if item.get("evidence_level") == "assumed" and item.get("critical")
    ]
    for item in active_rules:
        item.setdefault("evidence_level", "confirmed")
    truth_layers = collect_truth_layers(novel_dir, chapter)
    must_check = [
        "本章谁出现，逐一核对 characters.json 的动机、声纹、行为边界",
        "本章发生在哪些地点，核对 locations.json 的通勤、消费、权限",
        "本章涉及哪些势力，核对 factions.json 的资源与行动成本",
        "本章新增事实必须写入 chapter truth delta，不能只留在正文里",
    ]
    if unknown_facts:
        must_check.append(
            f"未知事实：{len(unknown_facts)} 条，其中 critical {len(critical_unknown)} 条；"
            "critical 未清空前禁止写正文"
        )
    if assumed_facts:
        must_check.append(
            f"假设事实：{len(assumed_facts)} 条 critical assumed；assumed 禁止进入正文"
        )
    if truth_layers["unrevealed_facts"]:
        must_check.append(
            f"未揭示事实：{len(truth_layers['unrevealed_facts'])} 条；"
            "角色只能使用 reader_known 和 character_knowledge，不能把作者真相写成角色已知"
        )
    return {
        "schema_version": "1.0",
        "generated_at": now_iso(),
        "chapter": chapter,
        "title": title or f"第{chapter}章",
        "inputs": {
            "truth_dir": rel(truth_dir(novel_dir), novel_dir),
            "novel_state": "novel_state.json",
        },
        "active_rules": active_rules,
        "chapter_budget": {
            "target": WORD_COUNT_TARGET,
            "min": int(word_range[0]),
            "max": int(word_range[1]),
            "scene_count": "5-6",
            "scene_size": "450-650 中文字符",
        },
        "unknown_facts": unknown_facts,
        "assumed_facts": assumed_facts,
        "evidence_policy": dict(EVIDENCE_POLICY),
        "truth_layers": truth_layers,
        "write_ready": not critical_unknown and not assumed_facts,
        "blockers": critical_unknown,
        "must_check_before_writing": must_check,
    }


def write_truth_brief(rule_stack: dict[str, Any], output: Path) -> None:
    lines = [
        f"# 第{rule_stack['chapter']:03d}章 真相约束简报",
        "",
        f"- 标题：{rule_stack.get('title', '')}",
        f"- 字数：{rule_stack['chapter_budget']['min']}-{rule_stack['chapter_budget']['max']}，首稿瞄准 {rule_stack['chapter_budget']['target']} 左右",
        "- 顺序：pre -> 正文 -> chapter_summary -> truth_delta -> post",
        "",
        "## 本章硬规则",
    ]
    for item in rule_stack.get("active_rules", []):
        lines.append(f"- [{item.get('level')}] {item.get('id')}: {item.get('rule')}")
    lines.extend(["", "## 证据分级", ""])
    lines.append("- confirmed：真相文件 / 细纲 / 上一章正文，可直接使用")
    lines.append("- inferred：题材惯例 / 风格 DNA，正文中必须能说明依据")
    lines.append("- assumed：模型猜测，禁止进入正文")
    assumed = rule_stack.get("assumed_facts") or []
    if assumed:
        lines.append("")
        lines.append("### 假设事实（写前必须补齐）")
        for item in assumed:
            lines.append(f"- {item.get('file')}: {item.get('reason')}")
    lines.extend(["", "## 未知事实（写前必须处理）", ""])
    unknown_facts = rule_stack.get("unknown_facts") or []
    if not unknown_facts:
        lines.append("- 无")
    else:
        for fact in unknown_facts:
            flag = "CRITICAL" if fact.get("critical") else "warning"
            entity = f" {fact.get('entity_id')}" if fact.get("entity_id") else ""
            field = f".{fact.get('field')}" if fact.get("field") else ""
            lines.append(
                f"- [{flag}] {fact.get('file')}{entity}{field}: {fact.get('reason')}"
            )
    layers = rule_stack.get("truth_layers") or {}
    lines.extend(["", "## 作者真相（不得让角色直接引用）", ""])
    author_truth = layers.get("author_truth") or []
    if not author_truth:
        lines.append("- 无")
    for item in author_truth[:16]:
        known = "读者已知" if item.get("reader_known") else "未揭示"
        lines.append(
            f"- [{known}] {item.get('type')}:{item.get('id')} {item.get('summary')}"
        )
    lines.extend(["", "## 读者已知", ""])
    reader_known = layers.get("reader_known") or []
    if not reader_known:
        lines.append("- 无")
    for item in reader_known[:16]:
        lines.append(f"- {item.get('type')}:{item.get('id')} {item.get('summary')}")
    lines.extend(["", "## 未揭示事实（禁止角色引用）", ""])
    unrevealed = layers.get("unrevealed_facts") or []
    if not unrevealed:
        lines.append("- 无")
    for item in unrevealed[:16]:
        lines.append(f"- {item.get('type')}:{item.get('id')} {item.get('summary')}")
    lines.extend(["", "## 写前自检", ""])
    for item in rule_stack.get("must_check_before_writing", []):
        lines.append(f"- {item}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _render_truth_layer(
    title: str,
    entries: list[dict[str, Any]],
    *,
    empty_text: str,
) -> str:
    lines = [
        f"# {title}",
        "",
        "> 自动生成，禁止手改；源数据是 `设定/真相文件/`。",
        "",
    ]
    if not entries:
        lines.append(empty_text)
        return "\n".join(lines) + "\n"
    for item in entries:
        kind = str(item.get("type") or "")
        identity = str(item.get("id") or "")
        summary = str(item.get("summary") or "")
        lines.append(f"- **{kind}:{identity}** {summary}")
        if item.get("reveal_status"):
            lines.append(f"  - 状态：{item['reveal_status']}")
        if item.get("reveal_chapter") is not None:
            lines.append(f"  - 章节：{item['reveal_chapter']}")
        if item.get("partial"):
            lines.append("  - 注意：仅部分揭示")
    return "\n".join(lines) + "\n"


def write_power_ladder_view(rule_stack: dict[str, Any], novel_dir: Path) -> Path:
    """Write the derived power/ability ladder ledger."""
    layers = rule_stack.get("truth_layers") or {}
    characters = layers.get("character_knowledge") or {}
    path = novel_dir / "追踪" / "战力阶梯.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 战力阶梯",
        "",
        "> 自动生成，禁止手改；源数据是 `设定/真相文件/characters.json`。",
        "",
    ]
    if not characters:
        lines.append("- 暂无角色战力记录。")
    for identity, character in characters.items():
        ladder = character.get("power_ladder") or []
        if not ladder:
            continue
        lines.append(f"## {character.get('name') or identity}")
        lines.append("")
        lines.append("| 层级 | 能力 | 代价 | 获得章 | 明确打不过谁 |")
        lines.append("|---|---|---|---|---|")
        for item in ladder:
            abilities = "、".join(str(value) for value in (item.get("abilities") or []) if str(value).strip())
            cannot = "、".join(str(value) for value in (item.get("cannot_beat") or []) if str(value).strip())
            lines.append(
                "| {level} | {abilities} | {cost} | {chapter} | {cannot} |".format(
                    level=item.get("level", ""),
                    abilities=abilities or "—",
                    cost=item.get("cost", "") or "—",
                    chapter=item.get("obtained_chapter", ""),
                    cannot=cannot or "—",
                )
            )
        lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


def write_truth_views(rule_stack: dict[str, Any], novel_dir: Path) -> list[Path]:
    """Write derived author-truth and reader-known Markdown views."""
    layers = rule_stack.get("truth_layers") or {}
    view_dir = novel_dir / "追踪" / "时间线"
    view_dir.mkdir(parents=True, exist_ok=True)
    author_path = view_dir / "作者真相.md"
    reader_path = view_dir / "读者已知.md"
    author_path.write_text(
        _render_truth_layer(
            f"作者真相 — 第{int(rule_stack.get('chapter', 0)):03d}章",
            layers.get("author_truth") or [],
            empty_text="- 无作者真相记录。",
        ),
        encoding="utf-8",
    )
    reader_path.write_text(
        _render_truth_layer(
            f"读者已知 — 第{int(rule_stack.get('chapter', 0)):03d}章",
            layers.get("reader_known") or [],
            empty_text="- 读者暂无已确认事实。",
        ),
        encoding="utf-8",
    )
    return [author_path, reader_path]


def delta_template(chapter: int, title: str = "") -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "chapter": chapter,
        "title": title or f"第{chapter}章",
        "status": "draft",
        "chapter_observations": [
            {
                "type": "character|location|faction|event|relationship|resource|foreshadowing",
                "entity_id": "待填写",
                "fact": "待填写：本章新确认或改变的事实",
                "evidence": "待填写：正文中的具体依据",
            }
        ],
        "proposed_updates": {
            "characters": [],
            "locations": [],
            "factions": [],
            "events": [],
            "relationships": [],
            "resources": [],
            "foreshadowing": [],
        },
        "continuity_risks": [
            "待填写：如果后续忘记本章事实，会造成什么漂移"
        ],
        "auto_extraction": {
            "review_status": "not_run",
            "candidate_count": 0,
            "source_report": "",
            "fingerprint": "",
            "review_note": "",
        },
        "review_note": "确认无误后把 status 改为 approved；若本章只巩固既有事实，仍需写观察，status 可为 no_changes。",
        "updated_at": now_iso(),
    }


def delta_path(novel_dir: Path, chapter: int) -> Path:
    return novel_dir / "摘要" / f"chapter_{chapter:03d}_truth_delta.json"


def validate_delta_file(novel_dir: Path, chapter: int, title: str = "", *, create_template: bool = False) -> dict[str, Any]:
    path = delta_path(novel_dir, chapter)
    if not path.exists() and create_template:
        save_json(path, delta_template(chapter, title))

    payload = load_json(path, None)
    failures: list[str] = []
    if not path.exists():
        failures.append("truth delta 不存在")
    elif not isinstance(payload, dict):
        failures.append("truth delta JSON 无效")
    else:
        if payload.get("chapter") != chapter:
            failures.append("chapter 字段不匹配")
        if payload.get("status") not in {"approved", "no_changes"}:
            failures.append("status 必须为 approved 或 no_changes")
        auto = payload.get("auto_extraction")
        if not isinstance(auto, dict):
            failures.append("auto_extraction 缺失：先运行 extract-delta 或 write_pipeline.py post 自动生成候选事实")
        else:
            review_status = str(auto.get("review_status", "")).strip()
            if review_status in {"", "not_run", "needs_review"}:
                failures.append("auto_extraction 候选事实未审查：确认候选后把 review_status 改为 reviewed/no_candidates")
            candidate_count = int(auto.get("candidate_count", 0) or 0)
            if review_status == "reviewed" and candidate_count > 0 and is_blank(auto.get("review_note")):
                failures.append("auto_extraction.review_note 不能为空：说明候选事实已采纳/驳回情况")
        observations = payload.get("chapter_observations")
        if not isinstance(observations, list) or len(observations) < 3:
            failures.append("chapter_observations 至少 3 条")
        else:
            for idx, item in enumerate(observations, 1):
                if not isinstance(item, dict):
                    failures.append(f"observation #{idx} 不是 object")
                    continue
                missing = [key for key in ("type", "entity_id", "fact", "evidence") if is_blank(item.get(key))]
                if missing:
                    failures.append(f"observation #{idx} 缺少: {', '.join(missing)}")
        if has_placeholder(payload):
            failures.append("仍含占位词")

    return {
        "generated_at": now_iso(),
        "path": rel(path, novel_dir),
        "status": "pass" if not failures else "fail",
        "failures": failures,
        "next": "补齐 chapter_observations、continuity_risks，并将 status 改为 approved/no_changes 后重跑 post。" if failures else "",
    }


TYPE_TO_FILE = {
    "character": "characters.json",
    "location": "locations.json",
    "faction": "factions.json",
    "event": "events.json",
    "relationship": "relationships.json",
    "resource": "resources.json",
    "foreshadowing": "foreshadowing.json",
}

KIND_TO_TYPE = {
    "characters": "character",
    "locations": "location",
    "factions": "faction",
    "events": "event",
    "relationships": "relationship",
    "resources": "resource",
    "foreshadowing": "foreshadowing",
}

EXTRACTION_KEYWORDS = {
    "character": [
        "决定", "意识到", "承认", "撒谎", "隐瞒", "答应", "拒绝", "失控", "底线",
        "工资", "收入", "房租", "住", "搬", "离职", "被裁", "面试", "加班", "技能",
        "能力", "擅长", "不会", "不能", "害怕", "想要", "习惯",
    ],
    "location": [
        "进入", "离开", "门禁", "监控", "租金", "房租", "通勤", "停车", "电梯",
        "保安", "消费", "距离", "搬", "住", "赶到", "楼下",
    ],
    "faction": [
        "安排", "调查", "封锁", "通知", "开除", "裁员", "打压", "合作", "收购",
        "报警", "起诉", "资源", "权限", "流程", "董事", "经理",
    ],
    "event": [
        "因为", "导致", "所以", "证据", "发现", "确认", "真相", "发生", "留下",
        "影响", "暴露", "推翻", "证明",
    ],
    "relationship": [
        "信任", "怀疑", "误会", "合作", "威胁", "求助", "背叛", "隐瞒", "告诉",
        "知道", "不知道", "骗", "保护", "欠", "救",
    ],
    "resource": [
        "钱", "现金", "银行卡", "合同", "钥匙", "手机", "电脑", "系统", "权限",
        "账号", "证据", "录音", "监控", "技能", "能力", "代价", "花了", "借",
    ],
    "foreshadowing": [
        "线索", "异常", "奇怪", "日记", "照片", "名片", "号码", "录音", "监控",
        "血迹", "账本", "钥匙", "暗号", "记号", "没注意", "总有一天", "迟早",
    ],
}

ACTION_KEYWORDS = [
    "说", "问", "告诉", "发现", "决定", "拒绝", "答应", "拿", "给", "去", "回",
    "离开", "进入", "出现", "失去", "得到", "知道", "隐瞒", "看见", "听见",
]

UNKNOWN_ENTITY_PATTERNS = [
    ("location_or_faction", re.compile(r"([\u4e00-\u9fffA-Za-z0-9]{2,24}(?:公司|集团|科技|医院|学校|小区|公寓|酒店|派出所|法院|律所|银行|基金|咖啡馆|便利店|网吧|城中村|写字楼))")),
    ("possible_person", re.compile(r"([\u4e00-\u9fff]{2,4})(?:说|问|笑|皱眉|点头|摇头|看着|站在|拿出|递给|推开|坐下)")),
]

FALSE_PERSON_NAMES = {
    "他们", "她们", "我们", "你们", "有人", "没人", "男人", "女人", "同事", "老板", "经理",
    "医生", "护士", "司机", "保安", "警察", "老师", "学生", "时候", "什么", "这里", "那里",
    "最后", "然后", "先让", "只问", "没有", "这个",
}

GENERIC_PLACE_OR_FACTION_NAMES = {
    "公司", "集团", "科技", "医院", "学校", "小区", "公寓", "酒店", "派出所", "法院",
    "律所", "银行", "基金", "咖啡馆", "便利店", "网吧", "城中村", "写字楼",
}

ENTITY_PREFIX_TRIM_MARKERS = [
    "回到", "来到", "赶到", "进入", "离开", "回过", "路过", "走进", "走出",
    "带来", "送到", "登录", "再登录", "看见", "看着", "发现", "在",
]

PERSON_TRAILING_NOISE = "只也又还都才就先没不正刚已会能想要"


def normalize_unknown_entity_name(name: str, type_hint: str) -> str:
    name = re.sub(r"^[，。！？、；：\s]+|[，。！？、；：\s]+$", "", name.strip())
    if type_hint == "location_or_faction":
        best = name
        for marker in ENTITY_PREFIX_TRIM_MARKERS:
            idx = best.rfind(marker)
            if idx >= 0:
                best = best[idx + len(marker):]
        return best.strip()
    if type_hint == "possible_person":
        return name.rstrip(PERSON_TRAILING_NOISE).strip()
    return name


def should_skip_unknown_entity(name: str, type_hint: str, known_names: set[str]) -> bool:
    if not name or name in known_names:
        return True
    if type_hint == "possible_person":
        return len(name) < 2 or name in FALSE_PERSON_NAMES or name.endswith(("的", "了"))
    if type_hint == "location_or_faction":
        return len(name) < 3 or name in GENERIC_PLACE_OR_FACTION_NAMES
    return False


def clean_sentence(text: str, max_len: int = 180) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"^#+\s*.*$", " ", text, flags=re.M)
    raw_parts = re.split(r"(?<=[。！？!?；;])\s*|\n+", text)
    sentences: list[str] = []
    for part in raw_parts:
        sentence = clean_sentence(part)
        if count_chinese_chars(sentence) >= 8:
            sentences.append(sentence)
    return sentences


def build_entity_catalog(novel_dir: Path) -> list[dict[str, Any]]:
    records = collect_records(novel_dir)
    catalog: list[dict[str, Any]] = []
    for kind, items in records.items():
        entity_type = KIND_TO_TYPE.get(kind, kind)
        for record in items:
            if not isinstance(record, dict):
                continue
            entity_id = str(record.get("id", "")).strip()
            name = str(record.get("name", "")).strip()
            if entity_type == "foreshadowing" and not name:
                name = clean_sentence(str(record.get("content", "")).strip(), 24)
            if entity_type == "resource" and not name:
                value = record.get("type")
                name = str(value).strip() if isinstance(value, str) and len(value) <= 16 else ""
            aliases = [item for item in {name, entity_id} if item and not has_placeholder(item)]
            prose_aliases = [item for item in aliases if not re.fullmatch(r"[a-z]+_\d+", item, re.I)]
            if not prose_aliases:
                continue
            catalog.append(
                {
                    "type": entity_type,
                    "id": entity_id or name,
                    "name": name or entity_id,
                    "aliases": sorted(prose_aliases, key=len, reverse=True),
                }
            )
    return catalog


def matched_keywords(sentence: str, entity_type: str) -> list[str]:
    keywords = EXTRACTION_KEYWORDS.get(entity_type, [])
    return [word for word in keywords if word in sentence]


def has_action(sentence: str) -> bool:
    return any(word in sentence for word in ACTION_KEYWORDS)


def candidate_fingerprint(report: dict[str, Any]) -> str:
    payload = {
        "candidate_observations": report.get("candidate_observations", []),
        "possible_new_entities": report.get("possible_new_entities", []),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def extract_delta_candidates(novel_dir: Path, chapter_file: Path, chapter: int, title: str = "") -> dict[str, Any]:
    text = read_text(chapter_file)
    sentences = split_sentences(text)
    catalog = build_entity_catalog(novel_dir)
    known_names = {alias for entity in catalog for alias in entity["aliases"]}
    known_mentions: dict[str, dict[str, Any]] = {}
    candidate_observations: list[dict[str, Any]] = []
    possible_new_entities: list[dict[str, Any]] = []
    seen_candidates: set[tuple[str, str, str]] = set()
    seen_unknown: set[tuple[str, str]] = set()

    for sentence in sentences:
        matches: list[dict[str, Any]] = []
        for entity in catalog:
            if any(alias and alias in sentence for alias in entity["aliases"]):
                matches.append(entity)
                known_mentions[entity["id"]] = {
                    "type": entity["type"],
                    "entity_id": entity["id"],
                    "entity_name": entity["name"],
                }

        for entity in matches:
            keywords = matched_keywords(sentence, entity["type"])
            if not keywords and not has_action(sentence):
                continue
            evidence = clean_sentence(sentence)
            key = (entity["type"], entity["id"], evidence)
            if key in seen_candidates:
                continue
            seen_candidates.add(key)
            reason = "、".join(keywords[:4]) if keywords else "出现动作/信息变化动词"
            candidate_observations.append(
                {
                    "type": entity["type"],
                    "entity_id": entity["id"],
                    "entity_name": entity["name"],
                    "fact": f"本章疑似更新了{entity['name']}的状态、行动或信息：{evidence}",
                    "evidence": evidence,
                    "reason": reason,
                    "confidence": 0.72 if keywords else 0.55,
                    "action": "审查属实后复制到 chapter_observations；不属实则在 auto_extraction.review_note 说明驳回。",
                }
            )

        character_matches = [entity for entity in matches if entity["type"] == "character"]
        if len(character_matches) >= 2 and matched_keywords(sentence, "relationship"):
            left, right = character_matches[0], character_matches[1]
            evidence = clean_sentence(sentence)
            entity_id = f"{left['id']}<->{right['id']}"
            key = ("relationship", entity_id, evidence)
            if key not in seen_candidates:
                seen_candidates.add(key)
                candidate_observations.append(
                    {
                        "type": "relationship",
                        "entity_id": entity_id,
                        "entity_name": f"{left['name']} / {right['name']}",
                        "fact": f"本章疑似改变或确认了{left['name']}与{right['name']}的关系/信息差：{evidence}",
                        "evidence": evidence,
                        "reason": "同句出现两名人物且包含关系变化关键词",
                        "confidence": 0.78,
                        "action": "审查属实后写入 relationship observation 或 proposed_updates.relationships。",
                    }
                )

        for type_hint, pattern in UNKNOWN_ENTITY_PATTERNS:
            for match in pattern.finditer(sentence):
                raw_name = match.group(1).strip()
                name = normalize_unknown_entity_name(raw_name, type_hint)
                if should_skip_unknown_entity(name, type_hint, known_names):
                    continue
                if "默" in name:
                    reason = "疑似新人物且含禁字“默”，必须改名"
                else:
                    reason = "正文出现但真相文件未登记"
                key = (type_hint, name)
                if key in seen_unknown:
                    continue
                seen_unknown.add(key)
                possible_new_entities.append(
                    {
                        "type_hint": type_hint,
                        "name": name,
                        "evidence": clean_sentence(sentence),
                        "reason": reason,
                        "action": "若是正式人物/地点/势力/资源，补入 truth_delta.proposed_updates；若只是临时称谓，在 review_note 说明。",
                    }
                )

    candidate_observations = sorted(
        candidate_observations,
        key=lambda item: (-float(item.get("confidence", 0)), item.get("type", ""), item.get("entity_id", "")),
    )[:60]
    possible_new_entities = possible_new_entities[:40]
    report: dict[str, Any] = {
        "schema_version": "1.0",
        "generated_at": now_iso(),
        "chapter": chapter,
        "title": title or f"第{chapter}章",
        "source_chapter_file": rel(chapter_file, novel_dir),
        "status": "review_required" if candidate_observations or possible_new_entities else "no_candidates",
        "summary": {
            "known_entity_mentions": len(known_mentions),
            "candidate_observations": len(candidate_observations),
            "possible_new_entities": len(possible_new_entities),
            "review_required": bool(candidate_observations or possible_new_entities),
        },
        "known_entity_mentions": sorted(known_mentions.values(), key=lambda item: (item["type"], item["entity_id"])),
        "candidate_observations": candidate_observations,
        "possible_new_entities": possible_new_entities,
        "review_instructions": [
            "先逐条审查候选事实是否真的改变了人物、地点、势力、事件、关系、资源或伏笔。",
            "属实的候选复制到 chapter_observations 或 proposed_updates。",
            "不属实的候选不用复制，但必须在 auto_extraction.review_note 写明已驳回原因。",
            "审查完成后把 auto_extraction.review_status 改为 reviewed；没有候选时保持 no_candidates。",
        ],
    }
    report["fingerprint"] = candidate_fingerprint(report)
    return report


def write_delta_candidates_markdown(report: dict[str, Any], output: Path) -> None:
    lines = [
        f"# 第{int(report['chapter']):03d}章 truth delta 候选事实",
        "",
        f"- 来源：{report.get('source_chapter_file', '')}",
        f"- 候选观察：{report['summary']['candidate_observations']}",
        f"- 疑似新实体：{report['summary']['possible_new_entities']}",
        "",
        "## 审查规则",
    ]
    for item in report.get("review_instructions", []):
        lines.append(f"- {item}")
    lines.extend(["", "## 候选观察"])
    for item in report.get("candidate_observations", [])[:30]:
        lines.append(f"- [{item.get('type')}] {item.get('entity_id')} / {item.get('entity_name')}：{item.get('fact')}")
        lines.append(f"  - 依据：{item.get('evidence')}")
        lines.append(f"  - 触发：{item.get('reason')}")
    if not report.get("candidate_observations"):
        lines.append("- 无")
    lines.extend(["", "## 疑似新实体"])
    for item in report.get("possible_new_entities", [])[:30]:
        lines.append(f"- [{item.get('type_hint')}] {item.get('name')}：{item.get('reason')}")
        lines.append(f"  - 依据：{item.get('evidence')}")
    if not report.get("possible_new_entities"):
        lines.append("- 无")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def patch_delta_with_candidates(novel_dir: Path, chapter: int, report: dict[str, Any], source_report: Path) -> dict[str, Any]:
    path = delta_path(novel_dir, chapter)
    payload = load_json(path, None)
    if not isinstance(payload, dict):
        payload = delta_template(chapter, str(report.get("title", "")))

    previous = payload.get("auto_extraction") if isinstance(payload.get("auto_extraction"), dict) else {}
    fingerprint = str(report.get("fingerprint", ""))
    candidate_count = int(report["summary"]["candidate_observations"]) + int(report["summary"]["possible_new_entities"])
    if candidate_count == 0:
        review_status = "no_candidates"
        review_note = "本章未提取到候选事实。"
    elif previous.get("fingerprint") == fingerprint and previous.get("review_status") == "reviewed":
        review_status = "reviewed"
        review_note = str(previous.get("review_note", ""))
    else:
        review_status = "needs_review"
        review_note = ""

    payload["auto_extraction"] = {
        "review_status": review_status,
        "candidate_count": candidate_count,
        "source_report": rel(source_report, novel_dir),
        "fingerprint": fingerprint,
        "candidate_observations": report.get("candidate_observations", [])[:20],
        "possible_new_entities": report.get("possible_new_entities", [])[:20],
        "review_note": review_note,
    }
    payload["updated_at"] = now_iso()
    save_json(path, payload)
    return {
        "status": "pass",
        "delta_path": rel(path, novel_dir),
        "review_status": review_status,
        "candidate_count": candidate_count,
    }


def apply_delta(novel_dir: Path, chapter: int) -> dict[str, Any]:
    path = delta_path(novel_dir, chapter)
    payload = load_json(path, None)
    if not isinstance(payload, dict):
        return {"status": "fail", "detail": "truth delta JSON 无效"}
    if payload.get("status") == "no_changes":
        return {"status": "skipped", "detail": "delta 标记为 no_changes"}
    if payload.get("status") != "approved":
        return {"status": "fail", "detail": "truth delta 未 approved"}

    observations = payload.get("chapter_observations", [])
    applied: list[str] = []
    for observation in observations:
        if not isinstance(observation, dict):
            continue
        obs_type = str(observation.get("type", "")).split("|", 1)[0].strip()
        file_name = TYPE_TO_FILE.get(obs_type)
        if not file_name:
            continue
        file_path = truth_dir(novel_dir) / file_name
        truth_payload = load_json(file_path, {})
        if not isinstance(truth_payload, dict):
            continue
        truth_payload.setdefault("chapter_facts", [])
        fact = deepcopy(observation)
        fact["chapter"] = chapter
        fact["synced_at"] = now_iso()
        truth_payload["chapter_facts"].append(fact)
        truth_payload["last_synced_chapter"] = chapter
        truth_payload["updated_at"] = now_iso()
        save_json(file_path, truth_payload)
        applied.append(file_name)

    proposed = payload.get("proposed_updates", {})
    if isinstance(proposed, dict):
        for kind, updates in proposed.items():
            if not updates:
                continue
            file_name = f"{kind}.json"
            file_path = truth_dir(novel_dir) / file_name
            truth_payload = load_json(file_path, {})
            if not isinstance(truth_payload, dict):
                continue
            truth_payload.setdefault("pending_updates", [])
            truth_payload["pending_updates"].append(
                {
                    "chapter": chapter,
                    "updates": updates,
                    "source_delta": rel(path, novel_dir),
                    "synced_at": now_iso(),
                }
            )
            truth_payload["updated_at"] = now_iso()
            save_json(file_path, truth_payload)
            applied.append(file_name)

    return {
        "status": "pass",
        "detail": f"已同步 {len(applied)} 项到真相文件",
        "files": sorted(set(applied)),
    }


def normalizer_task(chapter_text: str, chapter: int, title: str = "") -> dict[str, Any]:
    count = count_chinese_chars(chapter_text)
    if WORD_COUNT_MIN <= count <= WORD_COUNT_MAX:
        status = "pass"
        action = "none"
        needed = 0
    elif count < WORD_COUNT_MIN:
        status = "fail"
        action = "expand"
        needed = WORD_COUNT_TARGET - count
    else:
        status = "fail"
        action = "compress"
        needed = count - WORD_COUNT_TARGET

    return {
        "generated_at": now_iso(),
        "chapter": chapter,
        "title": title or f"第{chapter}章",
        "status": status,
        "word_count": count,
        "target_range": [WORD_COUNT_MIN, WORD_COUNT_MAX],
        "target": WORD_COUNT_TARGET,
        "action": action,
        "needed_chars": max(0, needed),
        "expansion_slots": [
            "观察：补足人物对环境、对方反应、资源限制的具体观察，不写空泛心理",
            "试探：让角色用一句话或一个小动作测试对方，产生新信息",
            "交锋：把冲突写成有来有回的选择，不只总结结果",
            "代价：补出行动成本、误解、损失或关系变化",
            "新线索：增加一个可回收的物证、信息差或伏笔",
        ],
        "rules": [
            "补写只能补有效剧情，不许靠水景物、复述、空泛心理凑字",
            "补写必须遵守 rule_stack 和真相文件",
            "补写后重新运行 write_pipeline.py post",
        ],
    }


def write_normalizer_markdown(task: dict[str, Any], output: Path) -> None:
    if task["status"] == "pass":
        return
    lines = [
        f"# 第{task['chapter']:03d}章 字数归一化任务",
        "",
        f"- 当前字数：{task['word_count']}",
        f"- 目标区间：{task['target_range'][0]}-{task['target_range'][1]}",
        f"- 动作：{task['action']}",
        f"- 需要调整：约 {task['needed_chars']} 中文字符",
        "",
        "## 可补写位置",
    ]
    for item in task["expansion_slots"]:
        lines.append(f"- {item}")
    lines.extend(["", "## 规则"])
    for item in task["rules"]:
        lines.append(f"- {item}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="故事真相文件管理器")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("scaffold", help="创建真相文件模板")
    p.add_argument("--novel-dir", required=True)
    p.add_argument("--title", default="")
    p.add_argument("--force", action="store_true")

    p = sub.add_parser("validate", help="校验真相文件")
    p.add_argument("--novel-dir", required=True)
    p.add_argument("--output", default="")

    p = sub.add_parser("compile", help="编译章节 rule_stack 和 truth brief")
    p.add_argument("--novel-dir", required=True)
    p.add_argument("--chapter", type=int, required=True)
    p.add_argument("--title", default="")
    p.add_argument("--output", default="")
    p.add_argument("--brief-output", default="")

    p = sub.add_parser("delta-template", help="创建章节 truth delta 模板")
    p.add_argument("--novel-dir", required=True)
    p.add_argument("--chapter", type=int, required=True)
    p.add_argument("--title", default="")
    p.add_argument("--force", action="store_true")

    p = sub.add_parser("validate-delta", help="校验章节 truth delta")
    p.add_argument("--novel-dir", required=True)
    p.add_argument("--chapter", type=int, required=True)
    p.add_argument("--title", default="")
    p.add_argument("--output", default="")
    p.add_argument("--create-template", action="store_true")

    p = sub.add_parser("extract-delta", help="从正文提取 truth delta 候选事实")
    p.add_argument("--novel-dir", required=True)
    p.add_argument("--chapter", type=int, required=True)
    p.add_argument("--title", default="")
    p.add_argument("--chapter-file", default="")
    p.add_argument("--output", default="")
    p.add_argument("--markdown-output", default="")
    p.add_argument("--patch-delta", action="store_true")

    p = sub.add_parser("apply-delta", help="把 approved delta 同步到真相文件")
    p.add_argument("--novel-dir", required=True)
    p.add_argument("--chapter", type=int, required=True)
    p.add_argument("--output", default="")

    p = sub.add_parser("normalize", help="生成字数归一化任务")
    p.add_argument("--novel-dir", required=True)
    p.add_argument("--chapter", type=int, required=True)
    p.add_argument("--title", default="")
    p.add_argument("--chapter-file", default="")
    p.add_argument("--output", default="")
    p.add_argument("--json-output", default="")

    args = parser.parse_args()
    novel_dir = resolve_path(args.novel_dir)

    if args.command == "scaffold":
        written = scaffold_truth_files(novel_dir, title=args.title, force=args.force)
        print(f"[OK] 真相文件模板已创建/更新: {len(written)}")
        for path in written:
            print(f" - {rel(path, novel_dir)}")
        return 0

    if args.command == "validate":
        report = validate_truth_files(novel_dir)
        if args.output:
            save_json(resolve_path(args.output), report)
        print(f"[{report['status'].upper()}] 真相文件校验: {report['passed']} pass / {report['failed']} fail")
        for item in report["results"]:
            marker = "[OK]" if item["status"] == "pass" else "[FAIL]"
            print(f"{marker} {item['file']} - {item['detail']}")
        return 0 if report["status"] == "pass" else 1

    if args.command == "compile":
        report = validate_truth_files(novel_dir)
        if report["status"] != "pass":
            print("[BLOCKED] 真相文件未通过校验，禁止编译章节 rule_stack。", file=sys.stderr)
            return 1
        stack = compile_rule_stack(novel_dir, args.chapter, args.title)
        output = resolve_path(args.output) if args.output else novel_dir / "摘要" / f"chapter_{args.chapter:03d}_rule_stack.json"
        brief = resolve_path(args.brief_output) if args.brief_output else novel_dir / "素材" / f"chapter_{args.chapter:03d}_truth_brief.md"
        save_json(output, stack)
        write_truth_brief(stack, brief)
        views = write_truth_views(stack, novel_dir)
        power_view = write_power_ladder_view(stack, novel_dir)
        views.append(power_view)
        print(f"[OK] rule_stack: {rel(output, novel_dir)}")
        print(f"[OK] truth_brief: {rel(brief, novel_dir)}")
        for view in views:
            print(f"[OK] truth view: {rel(view, novel_dir)}")
        layer_stats = stack.get("truth_layers", {}).get("stats", {})
        print(
            f"[OK] truth layers: author={layer_stats.get('author_truth', 0)} "
            f"reader={layer_stats.get('reader_known', 0)} "
            f"unrevealed={layer_stats.get('unrevealed', 0)}"
        )
        unknown = stack.get("unknown_facts") or []
        critical = [item for item in unknown if item.get("critical")]
        if unknown:
            print(
                f"[WARN] 未知事实 {len(unknown)} 条，critical {len(critical)} 条；"
                "critical 未清空前 pre_write_check 会阻断。",
                file=sys.stderr,
            )
            for item in critical:
                print(
                    f"  - {item.get('file')} {item.get('entity_id', '')} "
                    f"{item.get('field', '')}: {item.get('reason')}",
                    file=sys.stderr,
                )
        return 0

    if args.command == "delta-template":
        path = delta_path(novel_dir, args.chapter)
        if path.exists() and not args.force:
            print(f"[SKIP] 已存在: {rel(path, novel_dir)}")
            return 0
        save_json(path, delta_template(args.chapter, args.title))
        print(f"[OK] 已创建: {rel(path, novel_dir)}")
        return 0

    if args.command == "validate-delta":
        report = validate_delta_file(novel_dir, args.chapter, args.title, create_template=args.create_template)
        if args.output:
            save_json(resolve_path(args.output), report)
        print(f"[{report['status'].upper()}] truth delta: {report['path']}")
        for failure in report["failures"]:
            print(f"[FAIL] {failure}")
        if report["next"]:
            print(f"[NEXT] {report['next']}")
        return 0 if report["status"] == "pass" else 1

    if args.command == "extract-delta":
        chapter_file = resolve_path(args.chapter_file) if args.chapter_file else find_chapter_file(novel_dir, args.chapter)
        if not chapter_file or not chapter_file.exists():
            print(f"[FAIL] 未找到第{args.chapter}章正文", file=sys.stderr)
            return 1
        output = resolve_path(args.output) if args.output else novel_dir / "素材" / f"truth_delta_candidates_ch{args.chapter:03d}.json"
        md_output = resolve_path(args.markdown_output) if args.markdown_output else novel_dir / "素材" / f"truth_delta_candidates_ch{args.chapter:03d}.md"
        report = extract_delta_candidates(novel_dir, chapter_file, args.chapter, args.title)
        save_json(output, report)
        write_delta_candidates_markdown(report, md_output)
        patched = None
        if args.patch_delta:
            patched = patch_delta_with_candidates(novel_dir, args.chapter, report, output)
        print(
            f"[{report['status'].upper()}] 候选事实 {report['summary']['candidate_observations']} 条；"
            f"疑似新实体 {report['summary']['possible_new_entities']} 条"
        )
        print(f"[OK] 候选报告: {rel(output, novel_dir)}")
        print(f"[OK] 审查清单: {rel(md_output, novel_dir)}")
        if patched:
            print(f"[OK] 已写入 delta.auto_extraction: {patched['delta_path']} ({patched['review_status']})")
        return 0

    if args.command == "apply-delta":
        report = apply_delta(novel_dir, args.chapter)
        if args.output:
            save_json(resolve_path(args.output), report)
        print(f"[{report['status'].upper()}] {report['detail']}")
        return 0 if report["status"] in {"pass", "skipped"} else 1

    if args.command == "normalize":
        chapter_file = resolve_path(args.chapter_file) if args.chapter_file else find_chapter_file(novel_dir, args.chapter)
        if not chapter_file or not chapter_file.exists():
            print(f"[FAIL] 未找到第{args.chapter}章正文", file=sys.stderr)
            return 1
        task = normalizer_task(read_text(chapter_file), args.chapter, args.title)
        if args.json_output:
            save_json(resolve_path(args.json_output), task)
        output = resolve_path(args.output) if args.output else novel_dir / "素材" / f"chapter_{args.chapter:03d}_normalizer_task.md"
        write_normalizer_markdown(task, output)
        print(f"[{task['status'].upper()}] 字数 {task['word_count']} / 目标 {WORD_COUNT_MIN}-{WORD_COUNT_MAX}")
        if task["status"] != "pass":
            print(f"[NEXT] 已生成补写/压缩任务: {rel(output, novel_dir)}")
        return 0 if task["status"] == "pass" else 1

    return 1


if __name__ == "__main__":
    sys.exit(main())
