"""Single source of truth for quality thresholds.

Scripts import from here instead of hard-coding numbers in multiple files.
Platform word ranges are read from ``knowledge_base/60_Platform/_PROFILES.json``
when available; the constants below are the generic fallback.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .jsonio import load_json

# Chapter length (Chinese characters)
WORD_COUNT_MIN = 2800
WORD_COUNT_MAX = 3200
WORD_COUNT_TARGET = 3000

# Pre-write and review gates
PRE_WRITE_PASS = 70
REVIEW_PASS = 70

# Audit thresholds
DIALOGUE_RATIO_MIN = 0.25
REPEAT_RATIO_MAX = 0.25
SINGLE_LINE_PARAGRAPH_MAX = 200
CONCENTRATION_PER_CHAPTER = 5
TOTAL_AI_WORDS_PER_CHAPTER = 30
DASH_PER_1000_MAX = 2.38
COLON_PER_1000_MAX = 0.29
BARE_DIALOGUE_RATIO_MAX = 0.30
EMOTION_NAMING_MAX = 2
PARAGRAPH_UNIFORMITY_STREAK = 3
CHAPTER_END_TAIL_CHARS = 200
CONNECTOR_MAX_PER_1000 = 15
PASSIVE_MAX_RATIO = 0.08
DEGREE_ADVERB_CONSECUTIVE_MAX = 3
CLICHE_MAX_PER_1000 = 3
SENTENCE_ENDING_MAX_REPEAT = 5
TELL_MAX_PER_1000 = 8

# AI flavor score
AI_FLAVOR_WARN = 45
AI_FLAVOR_HIGH = 70

# Opening scorecard
OPENING_PASS = 70
OPENING_READY = 85

# Hit-rate model
HIT_RATE_GO = 85
HIT_RATE_FIX = 75
HIT_RATE_REBUILD = 60
HIT_VETO_CAP = 59
HIT_CEILING_CAP = 74

# Chapter rhythm
RHYTHM_SMALL_CLIMAX_EVERY = 3
RHYTHM_BIG_REVERSAL_EVERY = 10
RHYTHM_SAME_COOLPOINT_STREAK = 3
RHYTHM_WEAK_HOOK_STREAK = 3
RHYTHM_FIRST_CHAPTERS = 3
RHYTHM_IDENTITY_REVEAL_MIN_RATIO = 0.15
RHYTHM_RELEASE_WINDOW = 3

# Data diagnosis (Tomato defaults, 2026-08/09)
DATA_STAGE_WORDS = (80_000, 100_000, 200_000, 500_000, 1_000_000)
DATA_THRESHOLDS = {
    "shelf_excellent": 5.0,
    "shelf_pass": 10.0,
    "shelf_warn": 18.0,
    "follow_excellent": 20.0,
    "follow_pass": 50.0,
    "follow_warn": 100.0,
    "ch10_completion": 8.0,
    "wan_completion": 15.0,
    "follow7": 12.0,
    "daily_words": 4000,
    "daily_words_show": 6000,
    "score": 8.0,
    "income": 1000.0,
}

_PLATFORM_FALLBACK: dict[str, dict[str, Any]] = {
    "番茄": {"word_count_range": [2800, 3200], "recommended_range": [2800, 3200]},
    "七猫": {"word_count_range": [2800, 3200], "recommended_range": [3000, 4000]},
    "起点": {"word_count_range": [2000, 4000], "recommended_range": [2000, 3000]},
    "知乎": {"word_count_range": [3000, 5000], "recommended_range": [3000, 5000]},
    "短篇小说": {"word_count_range": [2000, 5000], "recommended_range": [2000, 5000]},
    "generic": {"word_count_range": [WORD_COUNT_MIN, WORD_COUNT_MAX], "recommended_range": [WORD_COUNT_MIN, WORD_COUNT_MAX]},
}


def profiles_path() -> Path:
    return Path(__file__).resolve().parents[2] / "knowledge_base" / "60_Platform" / "_PROFILES.json"


def load_platform_profiles() -> dict[str, Any]:
    payload = load_json(profiles_path(), {})
    if isinstance(payload, dict) and isinstance(payload.get("profiles"), dict):
        return payload
    return {"profiles": {}, "default": _PLATFORM_FALLBACK["generic"]}


def platform_profile(platform: str = "") -> dict[str, Any]:
    payload = load_platform_profiles()
    profiles = payload.get("profiles") or {}
    name = platform.strip()
    if name in profiles:
        return dict(profiles[name])
    for key, value in profiles.items():
        aliases = value.get("aliases") or []
        if name in aliases:
            return dict(value)
    if name in _PLATFORM_FALLBACK:
        return dict(_PLATFORM_FALLBACK[name])
    default = payload.get("default")
    if isinstance(default, dict):
        return dict(default)
    return dict(_PLATFORM_FALLBACK["generic"])


def platform_word_range(platform: str = "") -> tuple[int, int]:
    profile = platform_profile(platform)
    value = profile.get("word_count_range") or [WORD_COUNT_MIN, WORD_COUNT_MAX]
    try:
        return int(value[0]), int(value[1])
    except (TypeError, ValueError, IndexError):
        return WORD_COUNT_MIN, WORD_COUNT_MAX


def platform_recommended_range(platform: str = "") -> tuple[int, int]:
    profile = platform_profile(platform)
    value = profile.get("recommended_range") or profile.get("word_count_range") or [WORD_COUNT_MIN, WORD_COUNT_MAX]
    try:
        return int(value[0]), int(value[1])
    except (TypeError, ValueError, IndexError):
        return WORD_COUNT_MIN, WORD_COUNT_MAX
