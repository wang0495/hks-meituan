"""CityFlow POI过滤模块。"""

from __future__ import annotations

import re
from typing import Any

from backend.services.emotion import (emotion_compatibility,
                                      emotion_compatibility_with_consecutive,
                                      fatigue_penalty)
from backend.services.time_utils import (parse_hours_to_minutes,
                                         parse_time_window)

# ---------------------------------------------------------------------------
# 1. 约束过滤器
# ---------------------------------------------------------------------------


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
    hard_constraints = user_intent.get("hard_constraints", [])
    budget_pp = user_intent.get("budget", {}).get("per_person", float("inf"))
    time_info = user_intent.get("time", {})

    queue_tol = _parse_queue_tolerance(hard_constraints)
    need_access = _need_accessible(hard_constraints)
    need_pet = _need_pet_friendly(hard_constraints)

    user_start, user_end = (
        parse_time_window(time_info) if time_info.get("start") else (0, 0)
    )

    result: list[dict[str, Any]] = []
    for poi in pois:
        # 时间窗：检查POI营业时间与用户出行时段是否有重叠
        # 只要POI在用户出行期间有营业时间即可，不要求覆盖整个时段
        hours_str = poi.get("constraints", {}).get("opening_hours", "") or poi.get(
            "business_hours", ""
        )
        if hours_str and user_start > 0 and user_end > 0:
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

        # 预算
        price = poi.get("avg_price", 0)
        if price > budget_pp * 1.2:
            print(f"[过滤] {poi['name']} - 价格{price} > 预算上限{budget_pp * 1.2:.0f}")
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
