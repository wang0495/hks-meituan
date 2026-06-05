"""Solver scoring functions - extracted from solver.py for maintainability."""

from __future__ import annotations

import logging
from typing import Any

from backend.services.economy import enrich_poi_economics

logger = logging.getLogger(__name__)

# Scoring constants
_ALPHA = 1.0  # travel time weight
_BETA = 2.0  # emotion phase match weight
_GAMMA = 0.5  # fatigue penalty weight
_DELTA = 1.5  # category diversity weight
_CAT_RATIO_HIGH = 0.4
_CAT_RATIO_LOW = 0.3


def _calc_tourist_relevance(poi: dict) -> float:
    """计算 POI 作为旅游目的地的相关性评分 (0~1)。"""
    from backend.services.solver import _NON_TOURIST_KEYWORDS, _TOURIST_KEYWORDS

    name = poi.get("name", "")
    category = poi.get("category", "")
    tags = poi.get("tags", [])
    rating = poi.get("rating", 0)
    scene_tags = poi.get("_scene_tags", [])

    if category == "酒店":
        return 0.0

    meaningful_tags = {
        "海滨",
        "山景",
        "公园",
        "夜景",
        "文化历史",
        "自然风光",
        "拍照出片",
        "打卡热点",
        "品质体验",
        "运动健身",
        "休闲放松",
        "亲子",
        "情侣",
        "网红店",
        "老字号",
    }
    weak_tags = {
        "餐饮",
        "购物",
        "美食",
        "住宿",
        "运动",
        "文化",
        "市区",
        "经济",
        "经典",
        "出片",
        "休闲",
        "其他",
        "经济实惠",
        "适合聚餐",
        "交通便利",
        "环境好",
        "性价比高",
        "品牌齐全",
        "打折",
        "味道正宗",
        "停车方便",
        "服务好",
        "排队",
        "免费",
        "分量足",
    }

    has_meaningful_tag = any(t in scene_tags for t in meaningful_tags)
    only_weak_tags = scene_tags and all(t in weak_tags for t in scene_tags)

    score = 0.5
    if has_meaningful_tag:
        score += 0.3
    elif only_weak_tags:
        score -= 0.3

    if any(kw in name for kw in _NON_TOURIST_KEYWORDS):
        return 0.3

    if any(kw in name for kw in _TOURIST_KEYWORDS):
        score += 0.2

    if rating >= 4.5:
        score += 0.15
    elif rating >= 4.0:
        score += 0.1

    if len(tags) >= 3:
        score += 0.1

    return max(0.0, min(1.0, score))


def _score_poi_for_phase(poi: dict, phase: dict) -> float:
    """计算POI对某情绪阶段的匹配分数。"""
    et = poi.get("emotion_tags", {})
    score = 0.0
    for dim, (lo, hi) in phase["target"].items():
        val = et.get(dim, 0.5)
        if lo <= val <= hi:
            score += 1.0
        else:
            score -= abs(val - (lo + hi) / 2)
    if poi.get("category") in phase.get("cats", []):
        score += 0.5
    return score


def _calc_same_type_penalty(poi: dict, route: list[dict[str, Any]]) -> float:
    """计算同类POI连续访问惩罚。"""
    if not route:
        return 0.0

    curr_cat = poi.get("category", "")
    consecutive = 0
    for prev_step in reversed(route):
        if prev_step["poi"].get("category", "") == curr_cat:
            consecutive += 1
        else:
            break

    penalty = 0.5 + consecutive * 1.0 if consecutive > 0 else 0.0

    cat_count = sum(1 for s in route if s["poi"].get("category", "") == curr_cat)
    cat_ratio = cat_count / len(route)
    if cat_ratio >= _CAT_RATIO_HIGH:
        penalty += 3.0
    elif cat_ratio >= _CAT_RATIO_LOW:
        penalty += 1.5

    return penalty


def _calc_scene_semantic_bonus(poi: dict[str, Any], scene_requirements: list[str]) -> float:
    """计算场景需求语义匹配加分。"""
    if not scene_requirements:
        return 0.0

    from backend.services.solver import _SCENE_SYNONYMS

    poi_text = (
        poi.get("name", "")
        + " "
        + " ".join(poi.get("tags", []))
        + " "
        + " ".join(poi.get("_scene_tags", []))
    )
    matched = 0
    for sr in scene_requirements:
        if sr in poi_text or any(syn in poi_text for syn in _SCENE_SYNONYMS.get(sr, [])):
            matched += 1

    from backend.services.solver import _SCENE_SEMANTIC_PHASE1_BONUS

    return matched * _SCENE_SEMANTIC_PHASE1_BONUS if matched > 0 else 0.0


def _calc_economy_score(
    poi: dict[str, Any],
    route: list[dict[str, Any]],
    max_pois: int,
    user_intent: dict[str, Any],
) -> float:
    """计算经济引擎评分（杠杆率+预算节奏）。"""
    enriched = enrich_poi_economics(poi)
    leverage = enriched.get("experience_leverage", "medium")

    score = 0.0
    route_pos = len(route) / max_pois if max_pois > 0 else 0
    if route_pos < 0.25 and poi.get("avg_price", 0) < 50:
        from backend.services.solver import _BUDGET_RHYTHM_OPENING_BONUS

        score -= _BUDGET_RHYTHM_OPENING_BONUS
    if route_pos > 0.75:
        from backend.services.solver import _BUDGET_RHYTHM_CLOSING_FACTOR

        ev = enriched.get("experience_value", 5.0)
        score -= ev * _BUDGET_RHYTHM_CLOSING_FACTOR

    from backend.services.solver import _ECONOMY_LEVERAGE_BONUS, _ECONOMY_LEVERAGE_PENALTY

    if leverage == "high":
        score -= _ECONOMY_LEVERAGE_BONUS
    elif leverage == "low":
        score += _ECONOMY_LEVERAGE_PENALTY

    budget_per_person = user_intent.get("budget", {}).get("per_person", 500)
    from backend.services.solver import (
        _BUDGET_TIGHT_LEVERAGE_BONUS,
        _BUDGET_TIGHT_THRESHOLD,
        _get_weight,
    )

    budget_strictness = _get_weight("budget_strictness", 1.0)
    if budget_per_person < _BUDGET_TIGHT_THRESHOLD * budget_strictness and leverage == "high":
        score -= _BUDGET_TIGHT_LEVERAGE_BONUS

    return score
