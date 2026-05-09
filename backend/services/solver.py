"""CityFlow TSPTW 情绪混合求解器。

5阶段求解：
1. 候选筛选（按意图category偏好 + 情绪匹配）
2. TW-Nearest Neighbor 贪心初始化（含时间窗可行性剪枝）
3. 2-opt 局部搜索改进
4. 呼吸空间插入（高兴奋POI之间插入休息节点）
5. 高潮收尾检查 + 输出组装
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from backend.services.cache import distance_cache
from backend.services.economy import enrich_poi_economics
from backend.services.emotion import (calculate_emotion_curve,
                                      chemical_reaction,
                                      emotion_compatibility, fatigue_penalty,
                                      sensory_alternation)
from backend.services.filters import filter_candidates
from backend.services.geo import (cache_key_distance, cache_key_travel_time,
                                  poi_distance, poi_travel_time)
from backend.services.time_utils import (format_time, get_poi_opening_hours,
                                         parse_time)

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

_ALPHA = 1.0  # 旅行时间权重
_BETA = 0.5  # 情绪评分权重（提高）
_GAMMA = 0.2  # 疲劳惩罚权重（可通过 solve_route 的 perception_ctx 动态调整）
_gamma_multiplier: float = 1.0  # 感知上下文调用的疲劳权重乘数，默认 1.0
_DELTA = 0.8  # 同类惩罚权重（大幅提高，强制多样性）
_EPSILON = 0.5  # category多样性权重

_REST_MINUTES = 30  # 休息停留时间（分钟）
_EXCITEMENT_THRESHOLD = 0.6  # 高兴奋度阈值
_TRANQUILITY_THRESHOLD = 0.7  # 高宁静度阈值
_REST_CATEGORIES = {"公园", "咖啡馆", "广场", "休息"}
_REST_CANDIDATE_TAGS = {"公园", "咖啡", "休息", "安静"}

# 用户偏好维度 → 情绪标签映射
_PREF_TO_EMOTION: dict[str, str] = {
    "culture": "culture_depth",
    "nature": "tranquility",
    "social": "sociability",
    "food": "excitement",
}

_MAX_POIS_BY_PACE: dict[str, int] = {
    "闲逛型": 4,
    "平衡型": 6,
    "特种兵型": 8,
}

# 经济引擎权重
_ECONOMY_LEVERAGE_BONUS = 0.3  # high leverage 奖励（分数越低越好）
_ECONOMY_LEVERAGE_PENALTY = 0.2  # low leverage 惩罚
_BUDGET_RHYTHM_OPENING_BONUS = 0.3  # 开场阶段低价奖励
_BUDGET_RHYTHM_CLOSING_FACTOR = 0.05  # 收尾阶段体验价值系数
_BUDGET_TIGHT_LEVERAGE_BONUS = 0.3  # 预算紧张时高杠杆额外奖励
_BUDGET_TIGHT_THRESHOLD = 100  # 预算紧张阈值（元/人）

# 情绪曲线7阶段（参考产品设计文档表格10成都示例）
_EMOTION_PHASES: list[dict] = [
    {"name": "宁静铺垫", "ratio": 0.15, "target": {"tranquility": (0.5, 1.0)}, "cats": ["文化", "运动"]},
    {"name": "温暖上升", "ratio": 0.15, "target": {"excitement": (0.3, 0.6)}, "cats": ["餐饮"]},
    {"name": "好奇探索", "ratio": 0.15, "target": {"surprise": (0.4, 1.0), "culture_depth": (0.3, 0.7)}, "cats": ["文化", "其他"]},
    {"name": "兴奋高潮", "ratio": 0.15, "target": {"excitement": (0.6, 1.0)}, "cats": ["运动", "购物", "餐饮"]},
    {"name": "沉淀呼吸", "ratio": 0.10, "target": {"tranquility": (0.5, 1.0)}, "cats": ["文化"]},
    {"name": "文化输入", "ratio": 0.15, "target": {"culture_depth": (0.6, 1.0)}, "cats": ["文化"]},
    {"name": "社交收尾", "ratio": 0.15, "target": {"excitement": (0.3, 0.7), "sociability": (0.4, 1.0)}, "cats": ["餐饮", "购物"]},
]


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
    # category匹配加分
    if poi.get("category") in phase["cats"]:
        score += 0.5
    return score

# category偏好映射：用户偏好 → 优先选择的category
_PREF_TO_CATEGORIES: dict[str, list[str]] = {
    "culture": ["文化", "景点"],
    "food": ["餐饮"],
    "nature": ["运动", "景点"],
    "social": ["餐饮", "购物"],
}

# 意图关键词 → preferred categories
_KEYWORD_CATEGORIES: dict[str, list[str]] = {
    "安静": ["文化", "景点", "餐饮"],
    "文化": ["文化"],
    "博物馆": ["文化"],
    "艺术": ["文化"],
    "展览": ["文化"],
    "咖啡": ["餐饮"],
    "美食": ["餐饮"],
    "吃": ["餐饮"],
    "公园": ["运动", "景点"],
    "散步": ["运动", "景点"],
    "自然": ["运动", "景点"],
    "爬山": ["运动"],
    "运动": ["运动"],
    "健身": ["运动"],
    "网红": ["文化", "购物", "餐饮"],
    "打卡": ["文化", "购物", "餐饮"],
    "拍照": ["文化", "景点"],
    "购物": ["购物"],
    "带娃": ["运动", "文化", "景点"],
    "孩子": ["运动", "文化", "景点"],
    "宠物": ["运动", "景点"],
    "退休": ["文化", "运动", "景点"],
    "情侣": ["文化", "餐饮", "景点"],
    "约会": ["文化", "餐饮", "景点"],
    "朋友": ["餐饮", "购物", "运动"],
}


# ---------------------------------------------------------------------------
# 距离/时间（带缓存的封装）
# ---------------------------------------------------------------------------


def estimate_distance(
    poi_a: dict[str, Any] | None, poi_b: dict[str, Any] | None
) -> float:
    """估算两点间实际道路距离（米）。None 安全。带缓存。"""
    if not poi_a or not poi_b:
        return 0.0
    cache_key = cache_key_distance(poi_a, poi_b)
    cached_val = distance_cache.get(cache_key)
    if cached_val is not None:
        return cached_val
    dist = poi_distance(poi_a, poi_b)
    distance_cache.set(cache_key, dist)
    return dist


def estimate_travel_time(
    poi_a: dict[str, Any] | None, poi_b: dict[str, Any] | None
) -> float:
    """估算两点间旅行时间（分钟）。None 安全。带缓存。"""
    if not poi_a or not poi_b:
        return 0.0
    cache_key = cache_key_travel_time(poi_a, poi_b)
    cached_val = distance_cache.get(cache_key)
    if cached_val is not None:
        return cached_val
    ttime = poi_travel_time(poi_a, poi_b)
    distance_cache.set(cache_key, ttime)
    return ttime


def estimate_steps(poi: dict[str, Any]) -> int:
    """根据停留时间和体力需求估算步数。"""
    stay_min = poi.get("avg_stay_min", 60)
    physical = poi.get("emotion_tags", {}).get("physical_demand", 0.5)
    return int(stay_min * 100 * physical)


# ---------------------------------------------------------------------------
# Phase 0: 候选筛选（按意图category偏好 + 情绪匹配）
# ---------------------------------------------------------------------------


def _get_preferred_categories(user_intent: dict[str, Any]) -> list[str]:
    """根据用户意图获取优先category列表。"""
    preferred: list[str] = []
    prefs = user_intent.get("preferences", {})

    # 从偏好维度推断
    for pref_key, pref_val in prefs.items():
        if pref_val > 0.5:
            cats = _PREF_TO_CATEGORIES.get(pref_key, [])
            for c in cats:
                if c not in preferred:
                    preferred.append(c)

    # 从hard_constraints推断
    hard_constraints = user_intent.get("hard_constraints", [])
    for c in hard_constraints:
        cats = _KEYWORD_CATEGORIES.get(c, [])
        for cat in cats:
            if cat not in preferred:
                preferred.append(cat)

    # 从group_type推断
    group_type = user_intent.get("group", {}).get("type", "")
    if group_type == "情侣":
        for cat in ["文化", "餐饮", "景点"]:
            if cat not in preferred:
                preferred.append(cat)
    elif group_type == "亲子":
        for cat in ["运动", "文化", "景点"]:
            if cat not in preferred:
                preferred.append(cat)
    elif group_type == "朋友":
        for cat in ["餐饮", "购物", "运动"]:
            if cat not in preferred:
                preferred.append(cat)
    elif group_type == "退休":
        for cat in ["文化", "运动", "景点"]:
            if cat not in preferred:
                preferred.append(cat)

    # 如果没有明确偏好，给一个默认
    if not preferred:
        preferred = ["文化", "餐饮", "运动", "景点"]

    return preferred


def _select_diverse_candidates(
    all_pois: list[dict[str, Any]],
    user_intent: dict[str, Any],
    max_candidates: int = 30,
) -> list[dict[str, Any]]:
    """按意图筛选候选POI，确保category多样性。

    策略：
    1. 先按城市筛选（同城市内规划）
    2. 从preferred categories中各选一些高评分POI
    3. 确保至少覆盖2种category
    4. 酒店类默认排除（不是出行目的地）
    """
    preferred_cats = _get_preferred_categories(user_intent)
    preferences = user_intent.get("preferences", {})

    # 酒店不是出行目的地，默认排除
    excluded_cats = {"酒店"}

    # 按城市筛选（取POI数量最多的城市）
    city_counts: dict[str, int] = {}
    for poi in all_pois:
        city = poi.get("city", "未知")
        city_counts[city] = city_counts.get(city, 0) + 1
    if city_counts:
        main_city = max(city_counts, key=city_counts.get)
        all_pois = [p for p in all_pois if p.get("city") == main_city]

    # 按category分组
    by_category: dict[str, list[dict]] = {}
    for poi in all_pois:
        cat = poi.get("category", "其他")
        if cat in excluded_cats:
            continue
        by_category.setdefault(cat, []).append(poi)

    # 从每个preferred category中选评分最高的
    selected: list[dict] = []
    used_ids: set[str] = set()

    # 先从最匹配的category中选，每个category至少选2个
    per_cat = max(2, max_candidates // max(len(preferred_cats), 1))
    for cat in preferred_cats:
        if cat in excluded_cats or cat not in by_category:
            continue
        pois_in_cat = by_category[cat]
        # 按评分排序
        pois_in_cat.sort(key=lambda p: p.get("rating", 0), reverse=True)
        for p in pois_in_cat[:per_cat]:
            if p["id"] not in used_ids:
                selected.append(p)
                used_ids.add(p["id"])

    # 如果不够，从其他category补充
    if len(selected) < max_candidates:
        for cat, pois_in_cat in by_category.items():
            if cat in excluded_cats or cat in preferred_cats:
                continue
            pois_in_cat.sort(key=lambda p: p.get("rating", 0), reverse=True)
            for p in pois_in_cat[:2]:
                if p["id"] not in used_ids and len(selected) < max_candidates:
                    selected.append(p)
                    used_ids.add(p["id"])

    return selected


# ---------------------------------------------------------------------------
# 时间窗检查
# ---------------------------------------------------------------------------


def _check_time_windows(route: list[dict[str, Any]]) -> bool:
    """检查路线中每一步的到达时间是否在 POI 营业时间内。"""
    for step in route:
        open_t, close_t = get_poi_opening_hours(step["poi"])
        arrival = parse_time(step["arrival_time"])
        if arrival < open_t or arrival > close_t:
            return False
    return True


def _recalculate_times(
    route: list[dict[str, Any]], start_time: str
) -> list[dict[str, Any]]:
    """按空间顺序重新计算路线中每一步的到达/出发时间。"""
    if not route:
        return route

    current_time = parse_time(start_time)
    prev_poi: dict[str, Any] | None = None
    new_route: list[dict[str, Any]] = []

    for step in route:
        poi = step["poi"]
        travel = estimate_travel_time(prev_poi, poi)
        arrival = current_time + timedelta(minutes=travel)

        # 处理等待开门
        open_t, _ = get_poi_opening_hours(poi)
        arrival_dt = parse_time(format_time(arrival))
        if arrival_dt < open_t:
            arrival = parse_time(format_time(open_t))

        stay = poi.get("avg_stay_min", 60)
        departure = arrival + timedelta(minutes=stay)

        new_route.append(
            {
                "poi": poi,
                "arrival_time": format_time(arrival),
                "departure_time": format_time(departure),
                "travel_from_prev": {
                    "distance_m": round(estimate_distance(prev_poi, poi)),
                    "time_min": round(travel),
                },
            }
        )

        current_time = departure
        prev_poi = poi

    return new_route


# ---------------------------------------------------------------------------
# 路线评分
# ---------------------------------------------------------------------------


def _evaluate_route(route: list[dict[str, Any]], user_intent: dict[str, Any]) -> float:
    """评估路线综合评分（越高越好）。"""
    score = 0.0
    preferences = user_intent.get("preferences", {})

    # 情绪匹配度（偏好维度映射到情绪标签）
    for step in route:
        emotion = step["poi"].get("emotion_tags", {})
        for pref_key, pref_val in preferences.items():
            emotion_key = _PREF_TO_EMOTION.get(pref_key, pref_key)
            score += emotion.get(emotion_key, 0) * pref_val

    # 情绪兼容性（相邻POI对）
    for i in range(len(route) - 1):
        score += emotion_compatibility(route[i]["poi"], route[i + 1]["poi"])

    # 疲劳惩罚
    if route:
        total_steps = sum(estimate_steps(s["poi"]) for s in route)
        score += fatigue_penalty(total_steps, len(route))

    # category多样性奖励
    categories = [s["poi"].get("category", "") for s in route]
    unique_cats = len(set(categories))
    score += unique_cats * 0.5

    # 连续同类惩罚
    for i in range(len(route) - 1):
        if route[i]["poi"].get("category") == route[i + 1]["poi"].get("category"):
            score -= 0.3

    return score


# ---------------------------------------------------------------------------
# Phase 1: TW-Nearest Neighbor 贪心初始化
# ---------------------------------------------------------------------------


def _phase1_initialize(
    candidates: list[dict[str, Any]],
    user_intent: dict[str, Any],
    start_time: str,
) -> list[dict[str, Any]]:
    """按情绪曲线阶段选POI（先苦后甜编排）。

    按_EMOTION_PHASES定义的7个阶段依次选POI，
    每个阶段从候选池中选最匹配该阶段情绪目标的POI。
    """
    route: list[dict[str, Any]] = []
    remaining = list(candidates)
    current_time = parse_time(start_time)
    current_poi: dict[str, Any] | None = None
    step_count = 0

    pace = user_intent.get("pace", "平衡型")
    max_pois = _MAX_POIS_BY_PACE.get(pace, 6)

    # 用户结束时间
    end_time_str = user_intent.get("time", {}).get("end")
    end_time = parse_time(end_time_str) if end_time_str else None

    # 按情绪阶段选POI
    phases = _EMOTION_PHASES
    phase_idx = 0

    while remaining and len(route) < max_pois and phase_idx < len(phases):
        phase = phases[phase_idx]
        best: dict[str, Any] | None = None
        best_score = float("inf")

        for poi in remaining:
            travel = estimate_travel_time(current_poi, poi)
            arrival = current_time + timedelta(minutes=travel)

            # 等待开门
            open_t, close_t = get_poi_opening_hours(poi)
            arrival_as_time = parse_time(format_time(arrival))
            wait = 0.0
            if arrival_as_time < open_t:
                wait = (open_t - arrival_as_time).total_seconds() / 60
                arrival_as_time = open_t

            # 剪枝：到达时间必须在关门之前
            if arrival_as_time > close_t:
                continue

            # 剪枝：到达时间不超过用户结束时间
            if end_time:
                arrival_minutes = arrival_as_time.hour * 60 + arrival_as_time.minute
                end_minutes = end_time.hour * 60 + end_time.minute
                if arrival_minutes - end_minutes > 120:
                    continue

            # 情绪阶段匹配分数
            phase_score = -_score_poi_for_phase(poi, phase)

            # 疲劳惩罚
            fatigue = fatigue_penalty(step_count, len(route))

            # 同类惩罚
            same_type = 0.0
            if route:
                last_cat = route[-1]["poi"].get("category", "")
                curr_cat = poi.get("category", "")
                if last_cat == curr_cat:
                    same_type = 0.8 if (len(route) >= 2 and route[-2]["poi"].get("category") == curr_cat) else 0.3

            # 化学反应评分
            reaction_score = 0.0
            if route:
                reaction_score = chemical_reaction(route[-1]["poi"], poi)

            # 感官交替评分
            sensory_score = sensory_alternation(
                [*route, {"poi": poi}]
            )

            score = (
                _ALPHA * (travel + wait)
                + _BETA * phase_score
                + _GAMMA * fatigue * _gamma_multiplier
                + _DELTA * same_type
                + 0.3 * reaction_score  # 化学反应权重
                + 0.2 * sensory_score  # 感官交替权重
            )

            # ---------- 经济引擎评分 ----------
            enriched = enrich_poi_economics(poi)
            leverage = enriched.get("experience_leverage", "medium")

            # 预算节奏：开场偏好低价，收尾偏好高体验价值
            route_pos = len(route) / max_pois if max_pois > 0 else 0
            if route_pos < 0.25 and poi.get("avg_price", 0) < 50:
                score -= _BUDGET_RHYTHM_OPENING_BONUS  # 开场低价奖励
            if route_pos > 0.75:
                ev = enriched.get("experience_value", 5.0)
                score -= ev * _BUDGET_RHYTHM_CLOSING_FACTOR  # 收尾高体验奖励

            # 体验杠杆率奖励/惩罚
            if leverage == "high":
                score -= _ECONOMY_LEVERAGE_BONUS
            elif leverage == "low":
                score += _ECONOMY_LEVERAGE_PENALTY

            # 预算紧张时高杠杆POI额外奖励
            budget_per_person = (
                user_intent.get("budget", {}).get("per_person", 500)
            )
            if budget_per_person < _BUDGET_TIGHT_THRESHOLD and leverage == "high":
                score -= _BUDGET_TIGHT_LEVERAGE_BONUS

            if score < best_score:
                best_score = score
                best = poi

        if best is None:
            phase_idx += 1
            continue

        # 计算最终时间
        travel = estimate_travel_time(current_poi, best)
        arrival = current_time + timedelta(minutes=travel)
        open_t, _ = get_poi_opening_hours(best)
        arrival_as_time = parse_time(format_time(arrival))
        if arrival_as_time < open_t:
            arrival = parse_time(format_time(open_t))

        stay = best.get("avg_stay_min", 60)
        departure = arrival + timedelta(minutes=stay)

        route.append(
            {
                "poi": best,
                "arrival_time": format_time(arrival),
                "departure_time": format_time(departure),
                "travel_from_prev": {
                    "distance_m": round(estimate_distance(current_poi, best)),
                    "time_min": round(travel),
                },
            }
        )

        current_time = departure
        current_poi = best
        step_count += estimate_steps(best)
        remaining.remove(best)
        phase_idx += 1  # 每阶段选1个POI后进入下一阶段

    return route


# ---------------------------------------------------------------------------
# Phase 1.5: 强制category多样性
# ---------------------------------------------------------------------------


def _enforce_category_diversity(
    route: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    user_intent: dict[str, Any],
    start_time: str = "09:00",
) -> list[dict[str, Any]]:
    """强制路线中至少有2种不同category。

    策略：如果路线中连续3个同category，用候选池中不同category的高评分POI替换第2个。
    """
    if len(route) < 3:
        return route

    used_ids = {s["poi"]["id"] for s in route}
    preferred_cats = _get_preferred_categories(user_intent)

    # 检查连续3个同类
    i = 0
    while i <= len(route) - 2:
        cat_i = route[i]["poi"].get("category", "")
        cat_next = route[i + 1]["poi"].get("category", "")

        if cat_i == cat_next and cat_i != "休息":
            # 找一个不同category的候选POI
            replacement = None
            for c in candidates:
                if (
                    c["id"] not in used_ids
                    and c.get("category") != cat_i
                    and c.get("category") not in {"酒店", "休息"}
                ):
                    replacement = c
                    break

            if replacement:
                # 检查替换POI的营业时间
                _, close_t = get_poi_opening_hours(replacement)
                travel = estimate_travel_time(route[i]["poi"], replacement)
                arrival = parse_time(route[i]["departure_time"]) + timedelta(minutes=travel)
                open_t, _ = get_poi_opening_hours(replacement)
                arrival_dt = parse_time(format_time(arrival))
                if arrival_dt < open_t:
                    arrival_dt = open_t
                if arrival_dt > close_t:
                    continue  # 替换POI已关门，尝试下一个

                # 替换route[i+1]
                used_ids.discard(route[i + 1]["poi"]["id"])
                if arrival_dt < open_t:
                    arrival = parse_time(format_time(open_t))
                stay = replacement.get("avg_stay_min", 60)
                departure = arrival + timedelta(minutes=stay)

                route[i + 1] = {
                    "poi": replacement,
                    "arrival_time": format_time(arrival),
                    "departure_time": format_time(departure),
                    "travel_from_prev": {
                        "distance_m": round(estimate_distance(route[i]["poi"], replacement)),
                        "time_min": round(travel),
                    },
                }
                used_ids.add(replacement["id"])
        i += 1

    # 重新计算时间
    route = _recalculate_times(route, start_time)
    return route


# ---------------------------------------------------------------------------
# Phase 2: 2-opt 局部搜索改进
# ---------------------------------------------------------------------------


def _phase2_improve(
    route: list[dict[str, Any]],
    user_intent: dict[str, Any],
    start_time: str = "09:00",
    max_iterations: int = 50,
) -> list[dict[str, Any]]:
    """2-opt 局部搜索改进。"""
    improved = True
    iteration = 0

    while improved and iteration < max_iterations:
        improved = False
        iteration += 1

        for i in range(len(route) - 1):
            for j in range(i + 2, len(route)):
                new_route = route[: i + 1] + route[i + 1 : j + 1][::-1] + route[j + 1 :]
                new_route = _recalculate_times(new_route, start_time)

                if _check_time_windows(new_route):
                    old_score = _evaluate_route(route, user_intent)
                    new_score = _evaluate_route(new_route, user_intent)
                    if new_score > old_score:
                        route = new_route
                        improved = True
                        break
            if improved:
                break

    return route


# ---------------------------------------------------------------------------
# Phase 3: 呼吸空间插入
# ---------------------------------------------------------------------------


def _find_rest_poi(
    candidates: list[dict[str, Any]], used_ids: set[str], ref_poi: dict[str, Any] | None = None
) -> dict[str, Any] | None:
    """从候选池中找一个休息型 POI（高宁静度）。"""

    def _is_rest(p: dict[str, Any]) -> bool:
        return (
            p.get("category") in _REST_CATEGORIES
            or any(t in _REST_CANDIDATE_TAGS for t in p.get("tags", []))
        ) and p.get("emotion_tags", {}).get("tranquility", 0) > _TRANQUILITY_THRESHOLD

    unused = [p for p in candidates if _is_rest(p) and p["id"] not in used_ids]
    if unused:
        return max(
            unused, key=lambda p: p.get("emotion_tags", {}).get("tranquility", 0)
        )

    # 兜底：生成合成休息节点（继承参考POI的坐标，避免距离计算错误）
    ref_lat = ref_poi.get("lat", 22.26) if ref_poi else 22.26
    ref_lng = ref_poi.get("lng", 113.58) if ref_poi else 113.58
    return {
        "id": f"_synth_rest_{len(used_ids)}",
        "name": "休息片刻",
        "category": "休息",
        "rating": 0,
        "avg_price": 0,
        "lat": ref_lat,
        "lng": ref_lng,
        "business_hours": "00:00-23:59",
        "tags": ["休息"],
        "queue_prone": False,
        "avg_stay_min": _REST_MINUTES,
        "emotion_tags": {
            "excitement": 0.0,
            "tranquility": 0.9,
            "sociability": 0.0,
            "culture_depth": 0.0,
            "surprise": 0.0,
            "physical_demand": 0.0,
        },
        "constraints": {
            "accessible": True,
            "pet_friendly": True,
            "queue_time_min": 0,
            "opening_hours": "00:00-23:59",
            "has_restroom": True,
        },
    }


def _insert_rest_at(
    route: list[dict[str, Any]],
    insert_pos: int,
    rest_poi: dict[str, Any],
) -> None:
    """在指定位置插入休息节点，更新时间。"""
    prev = route[insert_pos - 1]
    prev_departure = parse_time(prev["departure_time"])
    travel = estimate_travel_time(prev["poi"], rest_poi)
    arrival = prev_departure + timedelta(minutes=travel)
    departure = arrival + timedelta(minutes=_REST_MINUTES)

    new_step: dict[str, Any] = {
        "poi": rest_poi,
        "arrival_time": format_time(arrival),
        "departure_time": format_time(departure),
        "travel_from_prev": {
            "distance_m": round(estimate_distance(prev["poi"], rest_poi)),
            "time_min": round(travel),
        },
    }
    route.insert(insert_pos, new_step)


def _phase3_breathing(
    route: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    user_intent: dict[str, Any],
    start_time: str = "09:00",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """在连续高兴奋 POI 之间插入休息节点。"""
    breathing_spots: list[dict[str, Any]] = []
    used_ids = {s["poi"]["id"] for s in route}

    # 检测连续 3 个高兴奋 POI
    i = 0
    while i <= len(route) - 3:
        consecutive = all(
            route[i + j]["poi"].get("emotion_tags", {}).get("excitement", 0)
            > _EXCITEMENT_THRESHOLD
            for j in range(3)
        )

        if consecutive:
            rest = _find_rest_poi(candidates, used_ids, route[i]["poi"])
            if rest:
                insert_pos = i + 1
                _insert_rest_at(route, insert_pos, rest)
                breathing_spots.append(rest)
                used_ids.add(rest["id"])
                # 插入后立即重新计算后续时间
                route = _recalculate_times(route, start_time)
                i += 4
                continue
        i += 1

    # 闲逛型节奏：每 2 个原始 POI 插入一个休息
    if user_intent.get("pace") == "闲逛型" and len(route) >= 3:
        rest_ids = {s["poi"]["id"] for s in breathing_spots}
        original_indices = [
            i for i, s in enumerate(route) if s["poi"]["id"] not in rest_ids
        ]

        insert_after = [
            original_indices[i]
            for i in range(2, len(original_indices), 2)
            if i < len(original_indices)
        ]

        for idx in reversed(insert_after):
            if idx >= len(route):
                continue
            ref_poi = route[idx]["poi"] if idx < len(route) else None
            rest = _find_rest_poi(candidates, used_ids, ref_poi)
            if rest:
                insert_pos = idx + 1
                _insert_rest_at(route, insert_pos, rest)
                breathing_spots.append(rest)
                used_ids.add(rest["id"])
                # 插入后立即重新计算后续时间
                route = _recalculate_times(route, start_time)

    return route, breathing_spots


# ---------------------------------------------------------------------------
# Phase 4: 高潮收尾检查
# ---------------------------------------------------------------------------


def _phase4_finale(
    route: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """确保最后一个 POI 有足够的情绪高潮。"""
    if len(route) < 2:
        return route

    last_exc = route[-1]["poi"].get("emotion_tags", {}).get("excitement", 0)
    second_last_exc = route[-2]["poi"].get("emotion_tags", {}).get("excitement", 0)

    used_ids = {s["poi"]["id"] for s in route}

    if last_exc < second_last_exc * 0.8:
        better = [
            p
            for p in candidates
            if p.get("emotion_tags", {}).get("excitement", 0) > second_last_exc * 0.8
            and p.get("id") not in used_ids
        ]
        if better:
            # 按时间窗过滤：只保留到达时仍在营业的POI
            prev_departure = parse_time(route[-2]["departure_time"])
            time_ok = []
            for p in better:
                travel = estimate_travel_time(route[-2]["poi"], p)
                arrival = prev_departure + timedelta(minutes=travel)
                open_t, close_t = get_poi_opening_hours(p)
                arrival_dt = parse_time(format_time(arrival))
                if arrival_dt < open_t:
                    arrival_dt = open_t
                if arrival_dt <= close_t:
                    time_ok.append(p)

            if not time_ok:
                return route  # 无可用替换，保持原路线

            best = max(
                time_ok,
                key=lambda p: p.get("emotion_tags", {}).get("excitement", 0),
            )

            travel = estimate_travel_time(route[-2]["poi"], best)
            arrival = prev_departure + timedelta(minutes=travel)
            open_t, _ = get_poi_opening_hours(best)
            arrival_dt = parse_time(format_time(arrival))
            if arrival_dt < open_t:
                arrival = parse_time(format_time(open_t))
            departure = arrival + timedelta(minutes=best.get("avg_stay_min", 60))

            route[-1] = {
                "poi": best,
                "arrival_time": format_time(arrival),
                "departure_time": format_time(departure),
                "travel_from_prev": {
                    "distance_m": round(estimate_distance(route[-2]["poi"], best)),
                    "time_min": round(travel),
                },
            }

    return route


# ---------------------------------------------------------------------------
# Phase 5: 输出组装
# ---------------------------------------------------------------------------


def _phase5_assemble(
    route: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    breathing_spots: list[dict[str, Any]],
) -> dict[str, Any]:
    """组装最终输出。"""
    emotion_curve = calculate_emotion_curve(route)

    total_stay = 0.0
    total_travel = 0.0
    total_budget = 0
    total_steps = 0

    for step in route:
        arr = parse_time(step["arrival_time"])
        dep = parse_time(step["departure_time"])
        delta = (dep - arr).total_seconds() / 60
        total_stay += max(delta, 0)
        total_travel += step["travel_from_prev"]["time_min"]
        total_budget += step["poi"].get("avg_price", 0)
        total_steps += estimate_steps(step["poi"])

    used_ids = {s["poi"]["id"] for s in route}
    unused = [p for p in candidates if p["id"] not in used_ids]

    return {
        "route": route,
        "emotion_curve": emotion_curve,
        "total_cost": {
            "time_min": round(total_stay + total_travel),
            "budget_used": total_budget,
            "step_estimate": total_steps,
        },
        "unused_candidates": unused,
        "breathing_spots": breathing_spots,
    }


# ---------------------------------------------------------------------------
# 主求解函数
# ---------------------------------------------------------------------------


def solve_route(
    candidates: list[dict[str, Any]],
    user_intent: dict[str, Any],
    start_time: str = "09:00",
    perception_ctx: Any = None,
) -> dict[str, Any]:
    """求解最优路线。

    Args:
        candidates: 候选 POI 列表
        user_intent: 用户意图字典
        start_time: 出发时间，格式 "HH:MM"
        perception_ctx: 感知上下文（PerceptionContext），用于影响疲劳惩罚权重

    Returns:
        包含 route, emotion_curve, total_cost, unused_candidates, breathing_spots 的字典
    """
    # 感知上下文 → 动态调整疲劳惩罚权重
    global _gamma_multiplier
    gamma = _GAMMA
    if perception_ctx is not None:
        fatigue = getattr(perception_ctx, "fatigue_level", 0.0)
        if fatigue > 0.7:
            gamma = _GAMMA * 3.0  # 重度疲劳：权重 3 倍
            _gamma_multiplier = 3.0
        elif fatigue > 0.5:
            gamma = _GAMMA * 2.0  # 中度疲劳：权重 2 倍
            _gamma_multiplier = 2.0
        else:
            _gamma_multiplier = 1.0
    else:
        _gamma_multiplier = 1.0
    empty_result: dict[str, Any] = {
        "route": [],
        "emotion_curve": [],
        "total_cost": {"time_min": 0, "budget_used": 0, "step_estimate": 0},
        "unused_candidates": list(candidates),
        "breathing_spots": [],
    }

    if not candidates:
        return empty_result

    # Phase 0: 按意图筛选候选（确保category多样性）
    selected = _select_diverse_candidates(candidates, user_intent, max_candidates=30)

    # 约束过滤
    filtered = filter_candidates(selected, user_intent)

    if not filtered:
        # 如果过滤后没有候选，放宽约束再试
        filtered = filter_candidates(candidates[:100], user_intent)
        if not filtered:
            return empty_result

    # Phase 1: 贪心初始化
    route = _phase1_initialize(filtered, user_intent, start_time)

    if not route:
        return empty_result

    # Phase 1.5: 强制category多样性（替换连续同类POI）
    route = _enforce_category_diversity(route, filtered, user_intent, start_time)

    # Phase 2: 2-opt 局部改进
    route = _phase2_improve(route, user_intent, start_time)

    # Phase 3: 呼吸空间插入
    route, breathing_spots = _phase3_breathing(route, filtered, user_intent, start_time)

    # Phase 4: 高潮收尾检查
    route = _phase4_finale(route, filtered)

    # Phase 5: 输出组装
    return _phase5_assemble(route, filtered, breathing_spots)
