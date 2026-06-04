"""Synthesizer 餐饮管理模块。

确保路线中包含足够且多样的餐饮POI。
"""

from __future__ import annotations

from datetime import datetime, timedelta

from backend.agents_v3.experts.base import _haversine_km

# ── 餐饮子类型 ──
_FOOD_SCENE_SUBCATS: dict[str, list[str]] = {
    "海鲜": ["海鲜", "蚝", "鱼排", "渔港"],
    "正餐": ["餐厅", "烧", "煲", "火锅", "烧烤"],
    "小吃": ["粉", "面", "粥", "小吃", "排档"],
    "茶餐厅/甜品": ["茶餐厅", "甜品", "奶茶", "冰", "柠檬", "饮品"],
    "综合美食街": ["夜市", "美食街", "海鲜街", "老街"],
}
_FOOD_STOP_KEYWORDS = [
    "餐厅",
    "海鲜",
    "粉",
    "面",
    "粥",
    "甜品",
    "茶餐厅",
    "烧烤",
    "火锅",
    "夜市",
    "小吃",
    "排档",
    "肠粉",
]
_FOOD_STOP_CATEGORIES = {"餐饮", "美食", "小吃", "海鲜", "夜市", "夜市小吃"}
_MIN_FOOD_KEYWORDS = [
    "餐厅",
    "海鲜",
    "烧",
    "煲",
    "粉",
    "面",
    "粥",
    "甜品",
    "奶茶",
    "茶餐厅",
    "排档",
    "咖啡",
]
_MIN_FOOD_CATEGORIES = {"餐饮", "美食", "小吃", "海鲜", "夜市", "夜市小吃"}


def _get_route_name_set(steps: list[dict]) -> set[str]:
    """提取路线中所有POI名称集合（去重后）。"""
    from backend.agents_v3.nodes.synthesizer import _canonical_name

    return {_canonical_name(s.get("poi", {}).get("name", "")) for s in steps if s.get("poi")}


def _is_food_stop(step: dict) -> bool:
    """判断是否为餐饮站点。"""
    cat = step.get("poi", {}).get("category", "")
    if cat in _FOOD_STOP_CATEGORIES:
        return True
    return any(kw in step.get("poi", {}).get("name", "") for kw in _FOOD_STOP_KEYWORDS)


def _get_food_subcat(name: str) -> str:
    """获取餐饮子类型。"""
    for sub, kws in _FOOD_SCENE_SUBCATS.items():
        if any(kw in name for kw in kws):
            return sub
    return "其他"


def _find_missing_food(food_proposals: list[dict], route_names: set[str]) -> list[dict]:
    """找出路线中缺失的餐饮提案。"""
    missing = []
    for fp in food_proposals:
        name = fp.get("content", {}).get("name", "")
        if name in route_names:
            continue
        if any(name in rn or rn in name for rn in route_names):
            continue
        missing.append(fp)
    return missing


def _find_extra_food(
    food_proposals: list[dict],
    route_names: set[str],
    food_subcats: set[str],
    food_steps_count: int,
    max_total: int,
) -> list[dict]:
    """找出需要补充的餐饮候选。"""
    extra = []
    for fp in food_proposals:
        if len(extra) >= 3 or max_total + len(extra) >= 8:
            break
        name = fp.get("content", {}).get("name", "")
        if name in route_names:
            continue
        sub = _get_food_subcat(name)
        if sub in food_subcats and len(extra) >= max(0, 2 - food_steps_count):
            continue
        extra.append(fp)
        food_subcats.add(sub)
    return extra


def _ensure_food_in_route(route: dict, food_proposals: list[dict], intent: dict) -> dict:
    """确保路线中包含餐饮POI。"""
    from backend.agents_v3.nodes.synthesizer import _dedup_route

    if not route or not route.get("route") or not food_proposals:
        return route

    steps = route["route"]
    route_names = _get_route_name_set(steps)
    missing = _find_missing_food(food_proposals, route_names)

    if not missing:
        return route

    try:
        t = datetime.strptime(steps[-1].get("departure_time", "18:00"), "%H:%M")
    except ValueError:
        t = datetime.strptime("18:00", "%H:%M")

    try:
        end_dt = datetime.strptime(intent.get("time", {}).get("end", "21:00"), "%H:%M")
    except ValueError:
        end_dt = datetime.strptime("21:00", "%H:%M")

    for fp in missing:
        content = fp.get("content", {})
        departure = t + timedelta(minutes=50)
        if departure > end_dt or len(steps) >= 10:
            break

        meal_type = "dinner" if t >= datetime.strptime("15:00", "%H:%M") else "lunch"
        steps.append(
            {
                "poi": content,
                "arrival_time": t.strftime("%H:%M"),
                "departure_time": departure.strftime("%H:%M"),
                "travel_from_prev": {"distance_m": 1800, "time_min": 15},
                "_type": meal_type,
            }
        )
        t = departure + timedelta(minutes=15)

    steps = _dedup_route(steps)
    route["route"] = steps
    route["total_cost"] = {
        "time_min": route.get("total_cost", {}).get("time_min", 0),
        "budget_used": sum(s.get("poi", {}).get("avg_price", 0) for s in steps),
    }
    return route


def _ensure_food_scene_food_count(
    route: dict,
    food_proposals: list[dict],
    scene_type: str,
) -> dict:
    """美食型专用：确保路线至少含2个不同子类型的餐饮。"""
    if not route or not route.get("route") or not food_proposals or scene_type != "美食型":
        return route

    steps = route["route"]
    food_steps = [s for s in steps if _is_food_stop(s)]
    food_subcats = {_get_food_subcat(s.get("poi", {}).get("name", "")) for s in food_steps}

    if len(food_steps) >= 2 and len(food_subcats) >= 2:
        return route

    route_names = _get_route_name_set(steps)
    extra = _find_extra_food(food_proposals, route_names, food_subcats, len(food_steps), len(steps))

    if not extra:
        return route

    end_dt = datetime.strptime("21:00", "%H:%M")

    try:
        t = datetime.strptime(steps[-1].get("departure_time", "18:00"), "%H:%M")
    except ValueError:
        t = datetime.strptime("18:00", "%H:%M")

    for fp in extra:
        content = fp.get("content", {})
        arrival = t + timedelta(minutes=15)
        departure = arrival + timedelta(minutes=50)
        if departure > end_dt:
            break
        meal_type = "dinner" if arrival >= datetime.strptime("15:00", "%H:%M") else "lunch"
        steps.append(
            {
                "poi": content,
                "arrival_time": arrival.strftime("%H:%M"),
                "departure_time": departure.strftime("%H:%M"),
                "travel_from_prev": {"distance_m": 1800, "time_min": 15},
                "_type": meal_type,
            }
        )
        t = departure

    route["route"] = steps
    return route


def _has_food_in_route(steps: list[dict]) -> bool:
    """检查路线中是否已有餐饮。"""
    for s in steps:
        poi = s.get("poi", {})
        if (
            s.get("_type", "") in ("lunch", "dinner")
            or poi.get("category", "") in _MIN_FOOD_CATEGORIES
        ):
            return True
        if any(kw in poi.get("name", "") for kw in _MIN_FOOD_KEYWORDS):
            return True
    return False


def _find_best_food(
    food_proposals: list[dict], center_lat: float, center_lng: float
) -> dict | None:
    """找到最佳餐饮候选。"""
    best_food = None
    best_score = -1.0

    for fp in food_proposals:
        content = fp.get("content", {})
        if not content.get("rating") or content.get("category", "") in ("酒店", "住宿"):
            continue
        score = content.get("rating", 0)
        lat, lng = content.get("lat", 0), content.get("lng", 0)
        if lat and lng:
            dist = _haversine_km(lat, lng, center_lat, center_lng)
            if dist > 15:
                continue
            score -= dist * 0.1
        if score > best_score:
            best_score = score
            best_food = content

    return best_food


def _ensure_min_food_in_route(route: dict, food_proposals: list[dict], intent: dict) -> dict:
    """安全网：确保路线至少含1个餐饮。"""
    from backend.agents_v3.nodes.synthesizer import _dedup_route

    if not route or not route.get("route") or not food_proposals:
        return route

    steps = route["route"]
    if _has_food_in_route(steps):
        return route

    poi_coords = [
        (s["poi"].get("lat", 0), s["poi"].get("lng", 0))
        for s in steps
        if s.get("poi", {}).get("lat") and s.get("poi", {}).get("lng")
    ]
    if poi_coords:
        center_lat = sum(la for la, _ in poi_coords) / len(poi_coords)
        center_lng = sum(ln for _, ln in poi_coords) / len(poi_coords)
    else:
        center_lat, center_lng = 22.27, 113.58

    best_food = _find_best_food(food_proposals, center_lat, center_lng) or food_proposals[0].get(
        "content", {}
    )

    insert_idx = min(2, len(steps))
    if insert_idx > 0 and insert_idx < len(steps):
        prev = steps[insert_idx - 1]
        arrival = prev.get("departure_time", "12:00")
        try:
            t = datetime.strptime(arrival, "%H:%M") + timedelta(minutes=15)
        except ValueError:
            t = datetime.strptime("12:00", "%H:%M")
    elif insert_idx == 0 and steps:
        t_str = steps[0].get("arrival_time", "09:00")
        try:
            t = datetime.strptime(t_str, "%H:%M") + timedelta(minutes=120)
        except ValueError:
            t = datetime.strptime("12:00", "%H:%M")
    else:
        t = datetime.strptime("12:00", "%H:%M")

    meal_type = "dinner" if t >= datetime.strptime("15:00", "%H:%M") else "lunch"
    food_step = {
        "poi": best_food,
        "arrival_time": t.strftime("%H:%M"),
        "departure_time": (t + timedelta(minutes=50)).strftime("%H:%M"),
        "travel_from_prev": {"distance_m": 1500, "time_min": 15},
        "_type": meal_type,
    }
    steps.insert(insert_idx, food_step)
    steps = _dedup_route(steps)
    route["route"] = steps
    route["total_cost"] = {
        "time_min": route.get("total_cost", {}).get("time_min", 0),
        "budget_used": sum(s.get("poi", {}).get("avg_price", 0) for s in steps),
    }
    return route
