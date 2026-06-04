"""Synthesizer 时间管理模块。

路线时间分配、压缩、平滑等后处理函数。
"""

from __future__ import annotations

import contextlib
from datetime import datetime, timedelta

from backend.agents_v3.experts.base import _haversine_km

# ── 按类别的默认停留时间 ──
_CATEGORY_STAY: dict[str, int] = {
    "景点": 90,
    "文化": 90,
    "运动": 80,
    "自然风光": 75,
    "餐饮": 50,
    "美食": 50,
    "小吃": 35,
    "夜市小吃": 50,
    "咖啡馆": 35,
    "海景咖啡馆": 40,
    "甜品": 30,
    "酒吧": 75,
    "娱乐": 90,
    "购物": 60,
    "温泉SPA": 120,
    "水上运动场所": 90,
    "住宿": 0,
    "酒店": 0,
    "民宿": 0,
}
_LUNCH_EARLIEST = datetime.strptime("11:00", "%H:%M")
_DINNER_EARLIEST = datetime.strptime("17:00", "%H:%M")
_AFTERNOON_SPLIT = datetime.strptime("15:00", "%H:%M")
_NIGHT_KEYWORDS = ["夜市", "夜宵", "大排档", "深夜"]
_THEME_PARK_KW = ("长隆", "海洋王国", "游乐园", "主题公园", "乐园", "海洋科学馆", "水城")
_LANDMARK_KW = ("渔女", "灯塔", "观景台", "牌坊", "雕塑", "打卡", "地标", "邮局", "书店")
_MAX_STAY_BY_CATEGORY: dict[str, int] = {
    "景点": 120,
    "文化": 90,
    "公园": 90,
    "娱乐": 120,
    "餐饮": 75,
    "夜市": 60,
    "小吃": 50,
    "美食": 75,
}


def _category_stay_min(category: str) -> int:
    """Return default stay minutes for a POI category."""
    return _CATEGORY_STAY.get(category, 60)


def _shift_step_times(steps: list[dict], from_idx: int, shift_min: int) -> None:
    """从指定索引开始，偏移所有步骤的时间。"""
    for j in range(from_idx, len(steps)):
        try:
            a = datetime.strptime(steps[j]["arrival_time"], "%H:%M")
            d = datetime.strptime(steps[j]["departure_time"], "%H:%M")
            steps[j]["arrival_time"] = (a + timedelta(minutes=shift_min)).strftime("%H:%M")
            steps[j]["departure_time"] = (d + timedelta(minutes=shift_min)).strftime("%H:%M")
        except ValueError:
            pass


def _get_shift_target(step: dict) -> datetime | None:
    """获取步骤需要偏移到的目标时间。"""
    _type = step.get("_type", "")
    try:
        arrival = datetime.strptime(step["arrival_time"], "%H:%M")
    except ValueError:
        return None

    if _type == "lunch" and arrival < _LUNCH_EARLIEST:
        return _LUNCH_EARLIEST
    if _type == "dinner" and arrival < _DINNER_EARLIEST:
        return _DINNER_EARLIEST

    poi = step.get("poi", {})
    text = poi.get("name", "") + poi.get("category", "")
    if any(kw in text for kw in _NIGHT_KEYWORDS) and arrival < _DINNER_EARLIEST:
        return _DINNER_EARLIEST

    return None


def _fix_meal_types(steps: list[dict]) -> None:
    """修正lunch/dinner类型。"""
    for s in steps:
        _type = s.get("_type", "")
        if _type not in ("lunch", "dinner"):
            continue
        try:
            arrival = datetime.strptime(s["arrival_time"], "%H:%M")
        except ValueError:
            continue
        if _type == "dinner" and arrival < _AFTERNOON_SPLIT:
            s["_type"] = "lunch"
        elif _type == "lunch" and arrival >= _AFTERNOON_SPLIT:
            s["_type"] = "dinner"


def _enforce_time_windows(steps: list[dict]) -> list[dict]:
    """后处理：确保餐食和夜间场所在合理时间窗口内。"""
    if len(steps) <= 1:
        return steps

    try:
        first_arrival = datetime.strptime(steps[0]["arrival_time"], "%H:%M")
        if first_arrival >= datetime.strptime(
            "22:00", "%H:%M"
        ) or first_arrival < datetime.strptime("06:00", "%H:%M"):
            return steps
    except (ValueError, KeyError, IndexError):
        pass

    _fix_meal_types(steps)

    for _ in range(3):
        shifted = False
        for i, s in enumerate(steps):
            target = _get_shift_target(s)
            if target is None:
                continue

            try:
                arrival = datetime.strptime(s["arrival_time"], "%H:%M")
            except ValueError:
                continue

            if arrival >= target:
                continue

            _shift_step_times(steps, i, int((target - arrival).total_seconds() / 60))
            _fix_meal_types(steps[i:])
            shifted = True

        if not shifted:
            break

    return steps


def _calc_available_minutes(start_time: str, end_time: str) -> float:
    """计算可用时间（分钟）。"""
    try:
        return (
            datetime.strptime(end_time, "%H:%M") - datetime.strptime(start_time, "%H:%M")
        ).total_seconds() / 60
    except ValueError:
        return 720


def _recalc_route_times(steps: list[dict]) -> list[dict]:
    """重新计算路线中各步骤的到达/离开时间。"""
    if not steps:
        return steps

    start_time_str = steps[0].get("arrival_time", "09:00")
    try:
        t = datetime.strptime(start_time_str, "%H:%M")
    except ValueError:
        t = datetime.strptime("09:00", "%H:%M")

    prev_lat, prev_lng = 0.0, 0.0
    for step in steps:
        poi = step.get("poi", {})
        lat, lng = poi.get("lat", 0), poi.get("lng", 0)
        travel = (
            max(5, min(60, int(_haversine_km(prev_lat, prev_lng, lat, lng) * 8)))
            if prev_lat and lat
            else 15
        )

        t = t + timedelta(minutes=travel)
        stay = 50 if step.get("_type") in ("lunch", "dinner") else int(poi.get("avg_stay_min", 90))
        step["arrival_time"] = t.strftime("%H:%M")
        step["departure_time"] = (t + timedelta(minutes=stay)).strftime("%H:%M")
        step["travel_from_prev"] = {"distance_m": travel * 120, "time_min": travel}
        t = t + timedelta(minutes=stay)
        prev_lat, prev_lng = lat, lng

    return steps


def _compute_stay_min(step: dict, scene_type: str, pace: str) -> int:
    """规则化计算单站停留时间。优先用POI自身的avg_stay_min，按节奏调节。"""
    poi = step.get("poi", step)
    _type = step.get("_type", "")
    name = poi.get("name", "")

    if _type in ("lunch", "dinner"):
        return 55

    if scene_type == "目的地型" and any(kw in name for kw in _THEME_PARK_KW):
        return 240

    if any(kw in name for kw in _THEME_PARK_KW):
        return 180

    if any(kw in name for kw in _LANDMARK_KW):
        base = 30
        if "特种兵" in pace:
            return 15
        return base

    base_stay = int(poi.get("avg_stay_min", 60))
    if base_stay <= 0:
        base_stay = 60

    if "特种兵" in pace:
        return max(15, int(base_stay * 0.6))
    elif "闲逛" in pace or "慢" in pace:
        return int(base_stay * 1.2)

    return base_stay


def _compute_travel_min(prev_poi: dict, curr_poi: dict) -> int:
    """基于haversine距离计算站间交通时间。"""
    lat1, lng1 = prev_poi.get("lat", 0), prev_poi.get("lng", 0)
    lat2, lng2 = curr_poi.get("lat", 0), curr_poi.get("lng", 0)
    if lat1 and lng1 and lat2 and lng2:
        dist_km = _haversine_km(lat1, lng1, lat2, lng2)
        return max(5, min(45, int(dist_km * 3 + 5)))
    return 15


def _rule_assign_times(
    steps: list[dict],
    intent: dict,
    scene_type: str,
    pace: str = "平衡型",
) -> tuple[list[dict], list[dict]]:
    """纯规则时间分配。返回 (new_steps, dropped)。"""
    if not steps:
        return [], []

    start_time_str = intent.get("time", {}).get("start", "09:00")
    end_time_str = intent.get("time", {}).get("end", "21:00")

    try:
        cursor = datetime.strptime(start_time_str, "%H:%M")
        end_limit = datetime.strptime(end_time_str, "%H:%M")
    except ValueError:
        cursor = datetime.strptime("09:00", "%H:%M")
        end_limit = datetime.strptime("21:00", "%H:%M")

    new_steps: list[dict] = []
    dropped: list[dict] = []

    for i, step in enumerate(steps):
        stay = _compute_stay_min(step, scene_type, pace)

        if i > 0 and new_steps:
            prev_poi = new_steps[-1].get("poi", new_steps[-1])
            curr_poi = step.get("poi", step)
            travel = _compute_travel_min(prev_poi, curr_poi)
            cursor += timedelta(minutes=travel)
        else:
            travel = 0

        arrival = cursor
        departure = cursor + timedelta(minutes=stay)

        if departure > end_limit + timedelta(minutes=15):
            dropped.append(
                {
                    "name": step.get("poi", step).get("name", ""),
                    "reason": f"超出时间范围 (预计{departure.strftime('%H:%M')}>{end_time_str})",
                }
            )
            continue

        new_step = dict(step)
        new_step["arrival_time"] = arrival.strftime("%H:%M")
        new_step["departure_time"] = departure.strftime("%H:%M")
        new_step["stay_min"] = stay
        new_step["travel_from_prev"] = {"distance_m": travel * 120, "time_min": travel}
        new_steps.append(new_step)
        cursor = departure

    return new_steps, dropped


def _compress_abnormal_stays(steps: list[dict]) -> None:
    """压缩异常停留时间。"""
    for s in steps:
        stay = s.get("stay_min", 60)
        cat = s.get("poi", s).get("category", "")
        cap = 90
        for ck, limit in _MAX_STAY_BY_CATEGORY.items():
            if ck in cat:
                cap = limit
                break
        if stay > cap:
            s["stay_min"] = cap
            with contextlib.suppress(ValueError, KeyError):
                s["departure_time"] = (
                    datetime.strptime(s["arrival_time"], "%H:%M") + timedelta(minutes=cap)
                ).strftime("%H:%M")


def _fix_gaps_and_reversals(steps: list[dict]) -> None:
    """修正空窗和倒流。"""
    for i in range(1, len(steps)):
        try:
            prev_dep = datetime.strptime(steps[i - 1]["departure_time"], "%H:%M")
            curr_arr = datetime.strptime(steps[i]["arrival_time"], "%H:%M")
            gap_min = int((curr_arr - prev_dep).total_seconds() / 60)
        except (ValueError, KeyError):
            gap_min = 15

        if gap_min < 0 or gap_min > 45:
            prev_poi = steps[i - 1].get("poi", steps[i - 1])
            curr_poi = steps[i].get("poi", steps[i])
            lat1, lng1 = prev_poi.get("lat", 0), prev_poi.get("lng", 0)
            lat2, lng2 = curr_poi.get("lat", 0), curr_poi.get("lng", 0)
            travel_min = (
                max(5, min(45, int(_haversine_km(lat1, lng1, lat2, lng2) * 3 + 5)))
                if lat1 and lat2
                else 15
            )

            new_arr = prev_dep + timedelta(minutes=travel_min)
            steps[i]["arrival_time"] = new_arr.strftime("%H:%M")
            stay = max(1, steps[i].get("stay_min", 60))
            steps[i]["departure_time"] = (new_arr + timedelta(minutes=stay)).strftime("%H:%M")


def _compress_overflow(steps: list[dict], start_time: str, end_time: str) -> None:
    """等比压缩溢出的停留时间。"""
    try:
        last_dep = datetime.strptime(steps[-1]["departure_time"], "%H:%M")
        end_limit = datetime.strptime(end_time, "%H:%M")
    except (ValueError, KeyError):
        return

    if last_dep <= end_limit:
        return

    overflow_min = int((last_dep - end_limit).total_seconds() / 60)
    total_stay = sum(max(1, s.get("stay_min", 60)) for s in steps)
    if total_stay == 0:
        return

    ratio = max(0.5, 1 - overflow_min / total_stay)
    try:
        cursor = datetime.strptime(steps[0]["arrival_time"], "%H:%M")
    except (ValueError, KeyError):
        cursor = datetime.strptime(start_time, "%H:%M")

    for i, s in enumerate(steps):
        s["arrival_time"] = cursor.strftime("%H:%M")
        stay = max(15, int(s.get("stay_min", 60) * ratio))
        s["stay_min"] = stay
        cursor += timedelta(minutes=stay)
        s["departure_time"] = cursor.strftime("%H:%M")
        if i < len(steps) - 1:
            next_poi = steps[i + 1].get("poi", steps[i + 1])
            cur_poi = s.get("poi", s)
            lat1, lng1 = cur_poi.get("lat", 0), cur_poi.get("lng", 0)
            lat2, lng2 = next_poi.get("lat", 0), next_poi.get("lng", 0)
            cursor += (
                timedelta(
                    minutes=max(5, min(30, int(_haversine_km(lat1, lng1, lat2, lng2) * 3 + 5)))
                )
                if lat1 and lat2
                else timedelta(minutes=15)
            )

    try:
        if datetime.strptime(steps[-1]["departure_time"], "%H:%M") > end_limit:
            steps[-1]["departure_time"] = end_time
    except (ValueError, KeyError):
        pass


def _smooth_times(steps: list[dict], start_time: str, end_time: str) -> list[dict]:
    """后处理：修正LLM时间分配中的空窗、倒流、溢出、异常停留。"""
    if len(steps) <= 1:
        return steps

    _compress_abnormal_stays(steps)
    _fix_gaps_and_reversals(steps)
    _compress_overflow(steps, start_time, end_time)

    return steps
