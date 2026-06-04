"""Solver candidate selection functions - extracted from solver.py."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

# Category preferences
_PREF_TO_CATEGORIES: dict[str, list[str]] = {
    "culture": ["文化", "景点"],
    "food": ["餐饮"],
    "nature": ["运动", "景点"],
    "social": ["餐饮", "购物"],
}
_KEYWORD_CATEGORIES: dict[str, list[str]] = {
    "安静": ["文化", "景点", "餐饮"],
    "文化": ["文化"],
    "博物馆": ["文化"],
    "历史": ["文化"],
    "美食": ["餐饮"],
    "海鲜": ["餐饮"],
    "夜市": ["餐饮"],
    "小吃": ["餐饮"],
    "自然": ["运动", "景点"],
    "公园": ["运动", "景点"],
    "海边": ["景点"],
    "沙滩": ["景点"],
    "购物": ["购物"],
    "运动": ["运动"],
}
_GROUP_TYPE_CATEGORIES: dict[str, list[str]] = {
    "情侣": ["文化", "餐饮", "景点"],
    "亲子": ["运动", "文化", "景点"],
    "朋友": ["餐饮", "购物", "运动"],
    "退休": ["文化", "运动", "景点"],
}
_MACRO_CATS = ["文化", "餐饮", "运动", "景点", "购物"]
_MAX_CAT_RATIO_WITH_SCENE = 0.6
_MAX_CAT_RATIO_DEFAULT = 0.4

_SCENE_SYNONYMS: dict[str, list[str]] = {
    "茶馆": ["茶室", "茶舍", "品茶"],
    "咖啡馆": ["咖啡厅", "咖啡屋"],
    "书店": ["书吧", "阅读空间"],
    "酒吧": ["清吧", "夜店"],
    "火锅": ["涮锅", "麻辣烫"],
    "烧烤": ["烤肉", "BBQ"],
    "海鲜": ["海产", "水产"],
    "甜品": ["甜点", "蛋糕"],
    "奶茶": ["茶饮", "饮品"],
}
_VAGUE_LATE_NIGHT_SCENE_REQS = {"夜生活", "夜间活动", "夜游"}

_SCENE_SEMANTIC_PHASE1_BONUS = 2.0
_SCENE_MATCHED_PHASE1_BONUS = 3.0
_INPUT_SCENE_MATCH_BONUS = 2.0
_LLM_PLAN_PHASE1_BONUS = 2.0
_LLM_PREFERRED_BONUS = 1.5


def _get_preferred_categories(user_intent: dict[str, Any]) -> list[str]:
    """根据用户意图获取优先category列表。"""
    seen: set[str] = set()
    preferred: list[str] = []

    def _add(cats: list[str]) -> None:
        for c in cats:
            if c not in seen:
                seen.add(c)
                preferred.append(c)

    llm_cats = user_intent.get("preferred_categories", [])
    if llm_cats:
        _add(llm_cats)
        _add(_MACRO_CATS)
        return preferred

    prefs = user_intent.get("preferences", {})
    high_prefs = [k for k, v in prefs.items() if v > 0.5]
    for pref_key in high_prefs:
        _add(_PREF_TO_CATEGORIES.get(pref_key, []))

    for c in user_intent.get("hard_constraints", []):
        _add(_KEYWORD_CATEGORIES.get(c, []))

    group_type = user_intent.get("group", {}).get("type", "")
    _add(_GROUP_TYPE_CATEGORIES.get(group_type, []))

    if not preferred:
        return list(_MACRO_CATS)

    _add(["景点"])
    return preferred


def _select_diverse_filter_by_city(all_pois: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按POI数量最多的城市筛选。"""
    city_counts: dict[str, int] = {}
    for poi in all_pois:
        city_counts[poi.get("city", "未知")] = city_counts.get(poi.get("city", "未知"), 0) + 1
    if not city_counts:
        return all_pois
    main_city = max(city_counts, key=city_counts.get)
    return [p for p in all_pois if p.get("city", "未知") == main_city]


def _select_diverse_filter_tourist_quality(pois: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """过滤旅游质量低的POI。"""
    from backend.services.solver import _calc_tourist_relevance

    return [p for p in pois if _calc_tourist_relevance(p) >= 0.3]


def _select_diverse_filter_hard_constraints(
    pois: list[dict[str, Any]], hard_constraints: list[str]
) -> list[dict[str, Any]]:
    """按硬约束过滤。"""
    if not hard_constraints:
        return pois
    result = []
    for p in pois:
        name = p.get("name", "")
        skip = False
        for hc in hard_constraints:
            if hc == "indoor_only" and any(kw in name for kw in ["公园", "海滩", "海滨", "户外"]):
                skip = True
                break
            if hc == "outdoor_preferred" and any(kw in name for kw in ["室内", "商场", "购物中心"]):
                skip = True
                break
        if not skip:
            result.append(p)
    return result


def _matches_scene_requirement(poi: dict, scene_reqs: list[str]) -> bool:
    """检查POI是否匹配任意一个scene_requirement。"""
    text = (
        poi.get("name", "")
        + " "
        + " ".join(poi.get("tags", []))
        + " "
        + " ".join(poi.get("_scene_tags", []))
    )
    for sr in scene_reqs:
        if sr in text or any(syn in text for syn in _SCENE_SYNONYMS.get(sr, [])):
            return True
    return False


def _select_diverse_filter_scene_requirements(
    quality_pois: list[dict[str, Any]], user_intent: dict[str, Any], hard_constraints: list[str]
) -> list[dict[str, Any]]:
    """scene_requirements预过滤。"""
    scene_reqs = user_intent.get("scene_requirements", [])
    if (
        "late_night" in hard_constraints
        and scene_reqs
        and all(sr in _VAGUE_LATE_NIGHT_SCENE_REQS for sr in scene_reqs)
    ):
        scene_reqs = []
    if scene_reqs:
        matched = [p for p in quality_pois if _matches_scene_requirement(p, scene_reqs)]
        if len(matched) >= 3:
            return matched
    return quality_pois


def _get_scene_match_count(poi_text: str, scene_requirements: list[str]) -> int:
    """计算POI文本匹配的场景需求数量。"""
    matched = 0
    for sr in scene_requirements:
        if sr in poi_text or any(syn in poi_text for syn in _SCENE_SYNONYMS.get(sr, [])):
            matched += 1
    return matched


def _select_from_categories(
    by_category: dict[str, list[dict]],
    cats: list[str],
    excluded_cats: set[str],
    per_cat_max: int,
    max_candidates: int,
    mixed_score: Callable[[dict], float],
    selected: list[dict],
    used_ids: set[str],
) -> None:
    """从指定category列表中选择POI。"""
    for cat in cats:
        if cat in excluded_cats or cat not in by_category:
            continue
        pois_in_cat = sorted(by_category[cat], key=mixed_score, reverse=True)
        for p in pois_in_cat[:per_cat_max]:
            if p["id"] not in used_ids and len(selected) < max_candidates:
                selected.append(p)
                used_ids.add(p["id"])


def _select_diverse_select_by_category(
    quality_pois: list[dict[str, Any]],
    preferred_cats: list[str],
    excluded_cats: set[str],
    max_candidates: int,
    mixed_score: Callable[[dict], float],
    user_intent: dict[str, Any],
) -> list[dict[str, Any]]:
    """按category分组选择POI。"""
    by_category: dict[str, list[dict]] = {}
    for poi in quality_pois:
        cat = poi.get("category", "其他")
        if cat not in excluded_cats:
            by_category.setdefault(cat, []).append(poi)

    max_cat_ratio = (
        _MAX_CAT_RATIO_WITH_SCENE
        if user_intent.get("scene_requirements")
        else _MAX_CAT_RATIO_DEFAULT
    )
    per_cat_max = max(2, int(max_candidates * max_cat_ratio))
    selected: list[dict] = []
    used_ids: set[str] = set()

    _select_from_categories(
        by_category,
        preferred_cats,
        excluded_cats,
        per_cat_max,
        max_candidates,
        mixed_score,
        selected,
        used_ids,
    )

    if len(selected) < max_candidates:
        other_cats = [
            cat for cat in by_category if cat not in excluded_cats and cat not in preferred_cats
        ]
        _select_from_categories(
            by_category,
            other_cats,
            excluded_cats,
            2,
            max_candidates,
            mixed_score,
            selected,
            used_ids,
        )

    if not any(s.get("category") == "餐饮" for s in selected) and "餐饮" in by_category:
        for p in sorted(by_category["餐饮"], key=mixed_score, reverse=True)[:2]:
            if p["id"] not in used_ids and len(selected) < max_candidates:
                selected.append(p)
                used_ids.add(p["id"])

    return selected


def _select_diverse_dedup(selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """名称去重。"""
    seen: dict[str, dict] = {}
    result = []
    for p in selected:
        name = p.get("name", "").strip().lower()
        if name not in seen:
            seen[name] = p
            result.append(p)
    return result
