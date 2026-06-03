"""共享 SSE 辅助函数 -- 超时兜底、简化路线生成、SSE 消息构造。

从 backend.main / routers.v1.plan / routers.v2.plan / graphql.resolvers
提取的公共逻辑，消除跨文件重复。
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


async def with_timeout(coro, timeout_seconds: float = 12.0, fallback=None):
    """给协程加超时，超时返回 fallback。"""
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except TimeoutError:
        logger.warning("操作超时 (%.1fs)，使用兜底", timeout_seconds)
        return fallback


def generate_simplified_route(
    pois: list[dict[str, Any]], count: int = 3, start_time: str = "09:00"
) -> dict[str, Any]:
    """生成简化路线（兜底方案）。

    Args:
        pois: 候选 POI 列表。
        count: 最多取几个 POI。
        start_time: 起始时间，格式 "HH:MM"。

    Returns:
        包含 route / emotion_curve / total_cost 等字段的路线字典。
    """
    sorted_pois = sorted(pois, key=lambda p: p.get("rating", 0), reverse=True)[:count]
    try:
        sh, sm = start_time.split(":")
        start_h = int(sh)
        start_m = int(sm)
    except (ValueError, AttributeError):
        start_h, start_m = 9, 0
    return {
        "route": [
            {
                "poi": poi,
                "arrival_time": f"{(start_h + i) % 24:02d}:{start_m:02d}",
                "departure_time": f"{(start_h + i + 1) % 24:02d}:{start_m:02d}",
                "travel_from_prev": {"distance_m": 0, "time_min": 0},
            }
            for i, poi in enumerate(sorted_pois)
        ],
        "emotion_curve": [],
        "total_cost": {"time_min": 180, "budget_used": 0, "step_estimate": 3000},
        "unused_candidates": [],
        "breathing_spots": [],
    }


def sse(event: str, data_obj: Any) -> str:
    """构造一条 SSE 消息。"""
    return f"event: {event}\ndata: {json.dumps(data_obj, ensure_ascii=False)}\n\n"
