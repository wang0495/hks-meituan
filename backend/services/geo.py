"""CityFlow 地理计算公共模块。

提供 haversine 距离计算、道路距离估算、旅行时间估算等函数，
消除 solver.py / poi.py / vectorized.py 中的重复实现。
"""

from __future__ import annotations

import math
from typing import Any

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

_EARTH_RADIUS_M: float = 6_371_000.0
_ROAD_FACTOR: float = 1.3
_AVG_SPEED_KMH: float = 30.0


# ---------------------------------------------------------------------------
# 核心距离计算
# ---------------------------------------------------------------------------


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """计算两点间的球面距离（米）。

    Args:
        lat1: 第一个点的纬度
        lon1: 第一个点的经度
        lat2: 第二个点的纬度
        lon2: 第二个点的经度

    Returns:
        距离（米）
    """
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return _EARTH_RADIUS_M * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def haversine_with_road_factor(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    factor: float = _ROAD_FACTOR,
) -> float:
    """计算两点间的实际道路距离（米）。

    Args:
        lat1: 第一个点的纬度
        lon1: 第一个点的经度
        lat2: 第二个点的纬度
        lon2: 第二个点的经度
        factor: 道路系数（默认 1.3）

    Returns:
        实际道路距离（米）
    """
    return haversine(lat1, lon1, lat2, lon2) * factor


def estimate_travel_time(distance_m: float, speed_kmh: float = _AVG_SPEED_KMH) -> float:
    """估算旅行时间（分钟）。

    Args:
        distance_m: 距离（米）
        speed_kmh: 速度（千米/小时，默认 30）

    Returns:
        时间（分钟）
    """
    return distance_m / 1000.0 / speed_kmh * 60.0


# ---------------------------------------------------------------------------
# POI 级距离函数（带 None 安全和缓存键生成）
# ---------------------------------------------------------------------------


def poi_distance(poi_a: dict[str, Any] | None, poi_b: dict[str, Any] | None) -> float:
    """计算两个 POI 间的实际道路距离（米）。None 安全。

    Args:
        poi_a: 第一个 POI 字典（需含 lat, lng）
        poi_b: 第二个 POI 字典（需含 lat, lng）

    Returns:
        道路距离（米），任一输入为 None 时返回 0.0
    """
    if not poi_a or not poi_b:
        return 0.0
    return haversine_with_road_factor(poi_a["lat"], poi_a["lng"], poi_b["lat"], poi_b["lng"])


def poi_travel_time(poi_a: dict[str, Any] | None, poi_b: dict[str, Any] | None) -> float:
    """估算两个 POI 间的旅行时间（分钟）。None 安全。

    Args:
        poi_a: 第一个 POI 字典
        poi_b: 第二个 POI 字典

    Returns:
        旅行时间（分钟），任一输入为 None 时返回 0.0
    """
    return estimate_travel_time(poi_distance(poi_a, poi_b))


def cache_key_distance(poi_a: dict[str, Any], poi_b: dict[str, Any]) -> str:
    """生成距离缓存键。"""
    return f"dist:{poi_a.get('id', '')}:{poi_b.get('id', '')}"


def cache_key_travel_time(poi_a: dict[str, Any], poi_b: dict[str, Any]) -> str:
    """生成旅行时间缓存键。"""
    return f"ttime:{poi_a.get('id', '')}:{poi_b.get('id', '')}"
