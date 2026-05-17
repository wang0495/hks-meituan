"""CityFlow POI过滤模块。"""

from __future__ import annotations

import logging
import math
import re
from typing import Any

from backend.services.emotion import (emotion_compatibility,
                                      emotion_compatibility_with_consecutive,
                                      fatigue_penalty)
from backend.services.time_utils import (parse_time_window)

logger = logging.getLogger(__name__)

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
            logger.debug("位置过滤: %d个POI在半径内", len(pois))
            logger.debug("最近: %s (%skm)", pois[0]['name'], pois[0].get('distance_km', '?'))

    hard_constraints = user_intent.get("hard_constraints", [])
    budget_pp = user_intent.get("budget", {}).get("per_person", float("inf"))
    time_info = user_intent.get("time", {})

    queue_tol = _parse_queue_tolerance(hard_constraints)
    need_access = _need_accessible(hard_constraints)
    need_pet = _need_pet_friendly(hard_constraints)

    user_start, user_end = (
        parse_time_window(time_info) if time_info.get("start") else (0, 0)
    )

    # late_night场景：需要特殊处理营业时间检查
    _is_late_night = "late_night" in hard_constraints

    # 解析用户时间窗口（凌晨00:00的hour=0，不是None）
    user_start_h = user_start // 60
    user_end_h = user_end // 60 if user_end > 0 else None

    # 判断是否跨午夜时段（如00:00-06:00）
    _crosses_midnight = user_end < user_start or user_start_h >= 22 or user_start_h <= 6

    result: list[dict[str, Any]] = []
    for poi in pois:
        # 时间窗：检查POI营业时间与用户出行时段是否有重叠
        hours_str = poi.get("constraints", {}).get("opening_hours", "") or poi.get(
            "business_hours", ""
        )

        # 凌晨时段user_start=0，也需要检查营业时间（改为 >= 0）
        if hours_str and user_start >= 0 and user_end > 0:
            # 解析营业时间
            try:
                parts = hours_str.split("-")
                open_h = int(parts[0].strip().split(":")[0])
                open_m = int(parts[0].strip().split(":")[1])
                close_h = int(parts[1].strip().split(":")[0])
                close_m = int(parts[1].strip().split(":")[1])
                poi_open_min = open_h * 60 + open_m
                poi_close_min = close_h * 60 + close_m
            except (ValueError, AttributeError, IndexError):
                # 无法解析营业时间，检查标签判断是否24h
                tags_str = ' '.join(poi.get("tags", [])) + ' ' + poi.get("name", "")
                if "24小时" in tags_str or "通宵" in tags_str:
                    poi_open_min, poi_close_min = 0, 1439  # 24小时
                else:
                    poi_open_min, poi_close_min = 0, 1439  # 默认可用

            if _is_late_night and _crosses_midnight:
                # 深夜跨午夜场景：检查POI是否营业到深夜或在凌晨开门
                # 有效POI类型：
                # 1. 24小时营业 (00:00-23:59)
                # 2. 跨午夜营业 (如17:00-02:00, 18:00-05:00)
                # 3. 早开门覆盖凌晨时段 (如06:00-22:00 覆盖06:00结束时间)

                is_24h = (poi_open_min == 0 and poi_close_min >= 1439) or \
                         "24小时" in ' '.join(poi.get("tags", []))

                is_cross_midnight_poi = poi_close_min < poi_open_min  # POI跨午夜营业

                # 检查是否有交集
                if is_24h:
                    # 24小时营业POI始终可用
                    pass
                elif is_cross_midnight_poi:
                    # POI跨午夜营业：检查是否覆盖用户时段
                    # 用户时段 [user_start, user_end] 可能是00:00-360(06:00)
                    # POI营业时段 [poi_open, 1440) + [0, poi_close]
                    # 需要检查：(poi_open < user_end) OR (user_start < poi_close)
                    if not (poi_open_min < user_end or user_start < poi_close_min):
                        continue  # POI营业时段不覆盖用户时段
                else:
                    # 非跨午夜POI：营业时段 [poi_open, poi_close]
                    # 对于凌晨时段(如00:00-06:00)，白天营业的POI(09:00-22:00)不覆盖
                    # 检查是否有交集
                    if poi_open_min <= poi_close_min:
                        # 非跨午夜POI：只有当营业时段与用户时段有重叠才可用
                        if poi_close_min <= user_start or poi_open_min >= user_end:
                            continue  # POI营业时段不覆盖用户时段
            else:
                # 正常时段：检查是否有重叠
                if poi_close_min <= user_start or poi_open_min >= user_end:
                    continue

        # 排队
        q_time = poi.get("constraints", {}).get("queue_time_min", 0)
        if queue_tol is not None and q_time > queue_tol:
            logger.debug("%s - 排队%dmin > 容忍%dmin", poi['name'], q_time, queue_tol)
            continue

        # 无障碍
        if need_access and not poi.get("constraints", {}).get("accessible", False):
            logger.debug("%s - 不支持无障碍通行", poi['name'])
            continue

        # 宠物友好
        if need_pet and not poi.get("constraints", {}).get("pet_friendly", False):
            logger.debug("%s - 不支持宠物", poi['name'])
            continue

        # 预算（硬约束：超预算 1.0 倍直接排除）
        price = poi.get("avg_price", 0)
        if price > budget_pp * 1.0:
            logger.debug("%s - 价格%d > 预算%d", poi['name'], price, budget_pp)
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
