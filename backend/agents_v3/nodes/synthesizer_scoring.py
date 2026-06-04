"""Synthesizer 评分模块。

路线启发式评分函数，用于锦标赛组装时比较候选路线质量。
"""

from __future__ import annotations

from collections import Counter as _Counter
from datetime import datetime

from backend.agents_v3.experts.base import (
    _FOOD_CATEGORIES,
    _FOOD_KEYWORDS,
    _FOOD_SUBCATS,
    _LIANGCHA_KEYWORDS,
    _haversine_km,
)


def _get_route_name_set(steps: list[dict]) -> set[str]:
    """提取路线中所有POI名称集合（去重后）。"""
    from backend.agents_v3.nodes.synthesizer import _canonical_name

    return {_canonical_name(s.get("poi", {}).get("name", "")) for s in steps if s.get("poi")}


def _calc_geo_score(steps: list[dict]) -> float:
    """计算地理连续性分数 (0-25)。"""
    total_dist = 0.0
    max_segment = 0.0
    long_segments = 0

    for i in range(1, len(steps)):
        prev = steps[i - 1].get("poi", {})
        cur = steps[i].get("poi", {})
        lat1, lng1 = prev.get("lat", 0), prev.get("lng", 0)
        lat2, lng2 = cur.get("lat", 0), cur.get("lng", 0)
        if lat1 and lat2:
            d = _haversine_km(lat1, lng1, lat2, lng2)
            total_dist += d
            max_segment = max(max_segment, d)
            if d > 15:
                long_segments += 1

    score = max(0, 25 - total_dist * 0.5)
    if max_segment > 15:
        score -= (max_segment - 15) * 3
    if long_segments > 1:
        score -= (long_segments - 1) * 5
    return score


def _calc_diversity_score(steps: list[dict]) -> float:
    """计算类别多样性分数 (0-25)。"""
    categories = {
        s.get("poi", {}).get("category", "") for s in steps if s.get("poi", {}).get("category")
    }
    meal_types = {s.get("_type", "") for s in steps if s.get("_type")}
    score = min(25, (len(categories) + len(meal_types)) * 5)

    # 美食子类重复惩罚
    food_subcats = []
    for s in steps:
        name = s.get("poi", {}).get("name", "")
        cat = s.get("poi", {}).get("category", "")
        if cat in _FOOD_CATEGORIES or any(kw in name for kw in _FOOD_KEYWORDS):
            if any(kw in name for kw in _LIANGCHA_KEYWORDS):
                food_subcats.append("饮品/凉茶")
                continue
            for sub, kws in _FOOD_SUBCATS.items():
                if any(kw in name for kw in kws):
                    food_subcats.append(sub)
                    break
            else:
                food_subcats.append("其他餐饮")

    for cnt in _Counter(food_subcats).values():
        if cnt > 1:
            score -= (cnt - 1) * 2
    return score


def _calc_coverage_score(
    steps: list[dict], poi_proposals: list[dict], food_proposals: list[dict]
) -> float:
    """计算覆盖率分数 (0-20)。"""
    route_names = _get_route_name_set(steps)
    covered = sum(
        1
        for p in poi_proposals + food_proposals
        if any(
            p.get("content", {}).get("name", "") in rn or rn in p.get("content", {}).get("name", "")
            for rn in route_names
        )
    )
    total = len(poi_proposals) + len(food_proposals)
    return (covered / total * 20) if total > 0 else 0


def _calc_time_score(steps: list[dict], intent: dict) -> float:
    """计算时间利用率分数 (0-15)。"""
    try:
        first = datetime.strptime(steps[0]["arrival_time"], "%H:%M")
        last = datetime.strptime(steps[-1]["departure_time"], "%H:%M")
        route_min = (last - first).total_seconds() / 60
        available = (
            datetime.strptime(intent.get("time", {}).get("end", "21:00"), "%H:%M")
            - datetime.strptime(intent.get("time", {}).get("start", "09:00"), "%H:%M")
        ).total_seconds() / 60
        if available > 0:
            ratio = route_min / available
            if 0.8 <= ratio <= 1.0:
                return 15
            if 0.5 <= ratio < 0.8:
                return ratio * 15
            if ratio > 1.0:
                return max(0, 15 - (ratio - 1.0) * 30)
            return ratio * 10
        return 7
    except (ValueError, KeyError):
        return 7


def _calc_steps_score(steps: list[dict]) -> float:
    """计算步数合理性分数 (0-15)。"""
    n = len(steps)
    if 4 <= n <= 7:
        return 15
    if 3 <= n <= 8:
        return 10
    if n <= 10:
        return 5
    return max(-10, 5 - (n - 10) * 3)


def _score_route_heuristic(
    route: dict,
    poi_proposals: list[dict],
    food_proposals: list[dict],
    intent: dict,
) -> float:
    """启发式评分路线质量(0-100)，越高越好。不调LLM，纯规则。"""
    steps = route.get("route", [])
    if not steps:
        return -1.0

    return (
        _calc_geo_score(steps)
        + _calc_diversity_score(steps)
        + _calc_coverage_score(steps, poi_proposals, food_proposals)
        + _calc_time_score(steps, intent)
        + _calc_steps_score(steps)
    )
