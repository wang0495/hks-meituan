"""CityFlow POI过滤模块。"""

from __future__ import annotations

import logging
import math
import re
from typing import Any

from backend.services.emotion import (
    emotion_compatibility,
    emotion_compatibility_with_consecutive,
    fatigue_penalty,
)
from backend.services.time_utils import parse_time_window

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 0. 地理位置过滤器（by 王启龙 2026-05-09: POI筛选应基于用户位置就近规划）
# ---------------------------------------------------------------------------


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Haversine 公式计算两点间距离（公里）。"""
    earth_radius_km = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    )
    return earth_radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


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
    2. user_intent中显式的 location: "拱北" → 需要查表
    3. user_intent中的 city → 返回城市中心坐标
    4. 无位置信息 → 返回None
    """
    loc = user_intent.get("location")
    if isinstance(loc, dict):
        lat = loc.get("lat")
        lng = loc.get("lng")
        if lat is not None and lng is not None:
            return float(lat), float(lng)

    # 城市中心坐标映射
    city_centers: dict[str, tuple[float, float]] = {
        "珠海": (22.270, 113.543),
        "广州": (23.127, 113.357),
        "深圳": (22.543, 114.058),
        "佛山": (23.022, 113.122),
        "东莞": (23.020, 113.752),
        "中山": (22.517, 113.393),
        "江门": (22.579, 113.082),
        "湛江": (21.271, 110.359),
        "茂名": (21.661, 110.925),
        "肇庆": (23.047, 112.465),
        "惠州": (23.112, 114.416),
        "汕头": (23.354, 116.682),
        "潮州": (23.657, 116.622),
        "揭阳": (23.550, 116.373),
        "梅州": (24.289, 116.118),
        "韶关": (24.811, 113.598),
        "清远": (23.682, 113.051),
        "河源": (23.744, 114.700),
        "阳江": (21.858, 111.983),
        "云浮": (22.915, 112.044),
        "汕尾": (22.787, 115.376),
        "珠海横琴": (22.138, 113.539),
        "珠海拱北": (22.217, 113.553),
        "珠海香洲": (22.270, 113.543),
        "广州天河": (23.127, 113.357),
        "广州越秀": (23.125, 113.261),
        "深圳南山": (22.533, 113.930),
        "深圳福田": (22.522, 114.055),
    }

    # 地标坐标映射
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

    if isinstance(loc, str):
        if loc in landmarks:
            return landmarks[loc]
        if loc in city_centers:
            return city_centers[loc]

    # 从 user_intent["city"] 获取城市中心坐标
    city = user_intent.get("city")
    if city and city in city_centers:
        return city_centers[city]

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


def _parse_poi_business_hours(poi: dict[str, Any]) -> tuple[int, int]:
    """解析POI营业时间，返回 (open_min, close_min)。"""
    hours_str = poi.get("constraints", {}).get("opening_hours", "") or poi.get("business_hours", "")
    if not hours_str:
        return 0, 1439

    try:
        parts = hours_str.split("-")
        open_h = int(parts[0].strip().split(":")[0])
        open_m = int(parts[0].strip().split(":")[1])
        close_h = int(parts[1].strip().split(":")[0])
        close_m = int(parts[1].strip().split(":")[1])
        return open_h * 60 + open_m, close_h * 60 + close_m
    except (ValueError, AttributeError, IndexError):
        tags_str = " ".join(poi.get("tags", [])) + " " + poi.get("name", "")
        if "24小时" in tags_str or "通宵" in tags_str:
            return 0, 1439
        return 0, 1439


def _check_business_hours_overlap(
    poi: dict[str, Any],
    poi_open_min: int,
    poi_close_min: int,
    user_start: int,
    user_end: int,
    is_late_night: bool,
    crosses_midnight: bool,
) -> bool:
    """检查POI营业时间是否与用户时段重叠。返回True表示可用。"""
    if is_late_night and crosses_midnight:
        is_24h = (poi_open_min == 0 and poi_close_min >= 1439) or "24小时" in " ".join(
            poi.get("tags", [])
        )
        is_cross_midnight_poi = poi_close_min < poi_open_min

        if is_24h:
            return True
        if is_cross_midnight_poi:
            return poi_open_min < user_end or user_start < poi_close_min
        if poi_open_min <= poi_close_min:
            return not (poi_close_min <= user_start or poi_open_min >= user_end)
        return True
    return not (poi_close_min <= user_start or poi_open_min >= user_end)


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
    """
    user_lat, user_lng = _extract_user_location(user_intent)
    if user_lat is not None and user_lng is not None:
        pois = _filter_by_radius(pois, user_lat, user_lng)
        if pois:
            logger.debug("位置过滤: %d个POI在半径内", len(pois))
            logger.debug("最近: %s (%skm)", pois[0]["name"], pois[0].get("distance_km", "?"))

    hard_constraints = user_intent.get("hard_constraints", [])
    budget_pp = user_intent.get("budget", {}).get("per_person", float("inf"))
    time_info = user_intent.get("time", {})

    queue_tol = _parse_queue_tolerance(hard_constraints)
    need_access = _need_accessible(hard_constraints)
    need_pet = _need_pet_friendly(hard_constraints)

    user_start, user_end = parse_time_window(time_info) if time_info.get("start") else (0, 0)
    is_late_night = "late_night" in hard_constraints
    crosses_midnight = user_end < user_start or (user_start // 60) >= 22 or (user_start // 60) <= 6

    result: list[dict[str, Any]] = []
    for poi in pois:
        if user_start >= 0 and user_end > 0:
            poi_open_min, poi_close_min = _parse_poi_business_hours(poi)
            if not _check_business_hours_overlap(
                poi,
                poi_open_min,
                poi_close_min,
                user_start,
                user_end,
                is_late_night,
                crosses_midnight,
            ):
                continue

        q_time = poi.get("constraints", {}).get("queue_time_min", 0)
        if queue_tol is not None and q_time > queue_tol:
            logger.debug("%s - 排队%dmin > 容忍%dmin", poi["name"], q_time, queue_tol)
            continue

        if need_access and not poi.get("constraints", {}).get("accessible", False):
            logger.debug("%s - 不支持无障碍通行", poi["name"])
            continue

        if need_pet and not poi.get("constraints", {}).get("pet_friendly", False):
            logger.debug("%s - 不支持宠物", poi["name"])
            continue

        price = poi.get("avg_price", 0)
        if price > budget_pp * 1.2:
            logger.debug("%s - 价格%d > 预算%d", poi["name"], price, budget_pp)
            continue

        result.append(poi)

    return result


def check_hard_rules(
    intent: dict[str, Any], candidates: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """检查硬约束，返回违规列表。

    Args:
        intent: 用户意图字典
        candidates: 候选POI列表

    Returns:
        违规事件列表，每项含 rule/severity/description
    """
    violations: list[dict[str, Any]] = []
    budget = intent.get("budget", {}).get("per_person", 0)
    constraints = intent.get("hard_constraints", [])

    if budget > 0 and budget <= 300:
        over = [c for c in candidates if c.get("avg_price", 0) > budget * 1.2]
        if over:
            violations.append(
                {
                    "rule": "budget_hard",
                    "severity": "warning",
                    "description": f"{len(over)}个POI超过预算上限{int(budget*1.2)}元",
                }
            )

    if "accessible" in constraints:
        no_access = [c for c in candidates if not c.get("accessible", True)]
        if no_access:
            violations.append(
                {
                    "rule": "accessible",
                    "severity": "warning",
                    "description": f"{len(no_access)}个POI缺少无障碍设施",
                }
            )

    return violations


# ---------------------------------------------------------------------------
# 重新导出（向后兼容）
# ---------------------------------------------------------------------------

__all__ = [
    "check_hard_rules",
    "emotion_compatibility",
    "emotion_compatibility_with_consecutive",
    "fatigue_penalty",
    "filter_candidates",
]
