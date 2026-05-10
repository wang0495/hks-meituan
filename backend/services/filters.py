"""CityFlow POI过滤模块。"""

from __future__ import annotations

import math
import re
from typing import Any

from backend.services.emotion import (emotion_compatibility,
                                      emotion_compatibility_with_consecutive,
                                      fatigue_penalty)
from backend.services.time_utils import (parse_hours_to_minutes,
                                         parse_time_window)

# ---------------------------------------------------------------------------
# 0. 地理位置过滤器（by 王启龙 2026-05-09: POI筛选应基于用户位置就近规划）
# ---------------------------------------------------------------------------


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Haversine 公式计算两点间距离（公里）。"""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(
        math.radians(lat2)
    ) * math.sin(dlng / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


_DEFAULT_RADIUS_KM = 50.0  # 默认搜索半径


def _filter_by_radius(
    pois: list[dict[str, Any]],
    user_lat: float | None,
    user_lng: float | None,
    radius_km: float = _DEFAULT_RADIUS_KM,
) -> list[dict[str, Any]]:
    """按用户位置过滤POI，超出半径的排除。

    Args:
        pois: POI列表
        user_lat: 用户纬度
        user_lng: 用户经度
        radius_km: 搜索半径（公里）

    Returns:
        半径内的POI列表（包含 distance_km 字段）
    """
    if user_lat is None or user_lng is None:
        return pois  # 无位置信息时不过滤

    result = []
    for p in pois:
        lat = p.get("lat")
        lng = p.get("lng")
        if lat is None or lng is None:
            continue
        d = _haversine_km(user_lat, user_lng, lat, lng)
        if d <= radius_km:
            p["distance_km"] = round(d, 1)
            result.append(p)

    # 按距离排序（近至远）
    result.sort(key=lambda p: p.get("distance_km", 0))
    return result


def _extract_user_location(user_intent: dict) -> tuple[float | None, float | None]:
    """从用户意图中提取位置坐标。

    优先级：
    1. user_intent中显式的 location: {lat, lng}
    2. user_intent中显式的 location: "拱北" → 需要查表（暂不支持）
    3. 无位置信息 → 返回None
    """
    loc = user_intent.get("location")
    if isinstance(loc, dict):
        lat = loc.get("lat")
        lng = loc.get("lng")
        if lat is not None and lng is not None:
            return float(lat), float(lng)

    # 以下为常用地标（扩展时可移入配置文件）
    landmarks: dict[str, tuple[float, float]] = {
        "拱北": (22.217, 113.553),
        "香洲": (22.270, 113.543),
        "横琴": (22.138, 113.539),
        "金湾": (22.148, 113.363),
        "斗门": (22.208, 113.297),
        "吉大": (22.256, 113.577),
        "前山": (22.257, 113.514),
        "南屏": (22.222, 113.465),
        "广州塔": (23.106, 113.324),
        "天河": (23.127, 113.357),
        "越秀": (23.125, 113.261),
        "荔湾": (23.120, 113.237),
        "海珠": (23.090, 113.317),
        "白云": (23.162, 113.277),
        "番禺": (22.943, 113.369),
        "赤坎": (21.267, 110.376),
        "霞山": (21.194, 110.407),
    }
    if isinstance(loc, str) and loc in landmarks:
        return landmarks[loc]

    return None, None


def _parse_queue_tolerance(hard_constraints: list[str]) -> int | None:
    """从hard_constraints中解析排队容忍度（分钟）。格式如 '排队容忍度<10min'。"""
    for c in hard_constraints:
        m = re.search(r"排队容忍度\s*<\s*(\d+)\s*min", c)
        if m:
            return int(m.group(1))
    return None


def _need_accessible(hard_constraints: list[str]) -> bool:
    return any("无障碍" in c for c in hard_constraints)


def _need_pet_friendly(hard_constraints: list[str]) -> bool:
    return any("宠物" in c for c in hard_constraints)


def filter_candidates(
    pois: list[dict[str, Any]], user_intent: dict[str, Any]
) -> list[dict[str, Any]]:
    """根据用户意图过滤POI候选列表。

    过滤规则：
    - 位置：用户所在位置半径50km内（如有定位）
    - 时间窗：POI营业时间必须覆盖用户出行时段
    - 排队：poi排队时间 <= 用户排队容忍度
    - 无障碍：需要时过滤掉不支持的POI
    - 宠物友好：需要时过滤掉不支持的POI
    - 预算：avg_price 不超过 per_person 的1.2倍

    Args:
        pois: POI列表
        user_intent: 用户意图

    Returns:
        过滤后的POI列表
    """
    # 位置过滤（基于用户定位就近规划）
    user_lat, user_lng = _extract_user_location(user_intent)
    if user_lat is not None and user_lng is not None:
        pois = _filter_by_radius(pois, user_lat, user_lng)
        if pois:
            print(f"[过滤] 位置过滤: {len(pois)}个POI在半径内")
            print(f"[过滤] 最近: {pois[0]['name']} ({pois[0].get('distance_km', '?')}km)")

    hard_constraints = user_intent.get("hard_constraints", [])
    budget_pp = user_intent.get("budget", {}).get("per_person", float("inf"))
    time_info = user_intent.get("time", {})

    queue_tol = _parse_queue_tolerance(hard_constraints)
    need_access = _need_accessible(hard_constraints)
    need_pet = _need_pet_friendly(hard_constraints)

    user_start, user_end = (
        parse_time_window(time_info) if time_info.get("start") else (0, 0)
    )

    # late_night场景：跳过时间窗检查（Phase 0已做过深夜营业过滤）
    _skip_time_check = "late_night" in hard_constraints

    result: list[dict[str, Any]] = []
    for poi in pois:
        # 时间窗：检查POI营业时间与用户出行时段是否有重叠
        # 只要POI在用户出行期间有营业时间即可，不要求覆盖整个时段
        # late_night场景跳过此检查（Phase 0已做过深夜营业过滤）
        hours_str = poi.get("constraints", {}).get("opening_hours", "") or poi.get(
            "business_hours", ""
        )
        if hours_str and user_start > 0 and user_end > 0 and not _skip_time_check:
            open_m, close_m = parse_hours_to_minutes(hours_str)
            # 检查是否有重叠：POI关门时间 > 用户开始时间 AND POI开门时间 < 用户结束时间
            if close_m <= user_start or open_m >= user_end:
                continue

        # 排队
        q_time = poi.get("constraints", {}).get("queue_time_min", 0)
        if queue_tol is not None and q_time > queue_tol:
            print(f"[过滤] {poi['name']} - 排队{q_time}min > 容忍{queue_tol}min")
            continue

        # 无障碍
        if need_access and not poi.get("constraints", {}).get("accessible", False):
            print(f"[过滤] {poi['name']} - 不支持无障碍通行")
            continue

        # 宠物友好
        if need_pet and not poi.get("constraints", {}).get("pet_friendly", False):
            print(f"[过滤] {poi['name']} - 不支持宠物")
            continue

        # 预算（硬约束：超预算 1.0 倍直接排除）
        price = poi.get("avg_price", 0)
        if price > budget_pp * 1.0:
            print(f"[过滤] {poi['name']} - 价格{price} > 预算{budget_pp}")
            continue

        result.append(poi)

    return result


# ---------------------------------------------------------------------------
# 重新导出（向后兼容）
# ---------------------------------------------------------------------------

__all__ = [
    "filter_candidates",
    "emotion_compatibility",
    "emotion_compatibility_with_consecutive",
    "fatigue_penalty",
]
